import logging
from types import ModuleType
from urllib.parse import urlencode

import httpx
import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import SOCIAL_CODES
from app.core.database import get_db
from app.services import jwt_service, session_store, state_store, user_store
from app.services.activity import enqueue_activity
from app.services.oauth import apple, google, kakao, naver
from app.services.oauth.types import OAuthExchangeError
from app.services.user_store import SocialAccountAlreadyLinkedError

logger = logging.getLogger("app.auth")

router = APIRouter(prefix="/social-access")

# google/apple are wired up but not functional yet — no OAuth client credentials
# for either (Apple additionally needs a signed client-assertion JWT that isn't
# implemented, see app/services/oauth/apple.py). Naver/Kakao are the real ones.
_PROVIDERS: dict[str, ModuleType] = {"naver": naver, "kakao": kakao, "google": google, "apple": apple}


def _get_provider_module(provider: str) -> ModuleType:
    module = _PROVIDERS.get(provider)
    if module is None:
        raise HTTPException(status_code=404, detail=f"지원하지 않는 로그인 제공자입니다: {provider}")
    return module


def _frontend_redirect(**params: str | bool | None) -> RedirectResponse:
    query_params = {key: str(value) for key, value in params.items() if value is not None}
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?{urlencode(query_params)}")


@router.get("/{provider}/login")
async def login(provider: str) -> RedirectResponse:
    module = _get_provider_module(provider)
    state = await state_store.create_state()
    return RedirectResponse(module.build_authorize_url(state))


@router.post("/session")
async def activate_session(token: str) -> dict[str, str]:
    try:
        jwt_service.decode_user_id(token)
    except pyjwt.InvalidTokenError as error:
        logger.warning("session activation denied: reason=invalid_token")
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.") from error

    await session_store.set_active_token(token)
    return {"status": "ok"}


@router.get("/{provider}/link")
async def link(provider: str, token: str | None = None) -> RedirectResponse:
    module = _get_provider_module(provider)
    active_token = token or await session_store.get_active_token()
    if active_token is None:
        logger.warning("social link denied: reason=missing_active_session provider=%s", provider)
        raise HTTPException(status_code=401, detail="연동할 활성 세션 토큰이 없습니다. 먼저 로그인해주세요.")

    try:
        user_id = jwt_service.decode_user_id(active_token)
    except pyjwt.InvalidTokenError as error:
        logger.warning("social link denied: reason=invalid_token provider=%s", provider)
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.") from error

    state = await state_store.create_state(link_user_id=user_id)
    return RedirectResponse(module.build_authorize_url(state))


@router.get("/{provider}/callback")
async def callback(
    provider: str,
    state: str,
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    module = _get_provider_module(provider)

    state_entry = await state_store.verify_and_consume_state(state)
    if state_entry is None:
        logger.warning("social login denied: provider=%s reason=invalid_or_expired_state", provider)
        return _frontend_redirect(error="state 값이 유효하지 않거나 만료되었습니다.")

    if error is not None:
        # error/error_description are attacker-controlled query params on our own
        # callback URL — %r escapes them so they can't forge extra log lines.
        logger.warning(
            "social login denied: provider=%s reason=provider_error error=%r description=%r",
            provider,
            error,
            error_description,
        )
        return _frontend_redirect(error=f"{provider} 로그인이 취소되었거나 실패했습니다: {error_description or error}")

    if code is None:
        logger.warning("social login denied: provider=%s reason=missing_code", provider)
        return _frontend_redirect(error="인증 코드가 전달되지 않았습니다.")

    try:
        access_token = await module.exchange_code_for_token(code, state)
        profile = await module.fetch_profile(access_token)
    except (httpx.HTTPError, OAuthExchangeError) as exchange_error:
        logger.warning("social login denied: provider=%s reason=exchange_failed error=%r", provider, str(exchange_error))
        return _frontend_redirect(error=f"{provider} 로그인 요청이 실패했습니다: {exchange_error}")

    if state_entry.link_user_id is not None:
        try:
            user, newly_linked = await user_store.link_social_account(
                db,
                user_id=state_entry.link_user_id,
                provider=provider,
                provider_user_id=profile.provider_user_id,
                nickname=profile.nickname,
                email=profile.email,
                profile_image_url=profile.profile_image_url,
                gender=profile.gender,
                birthday=profile.birthday,
                birthyear=profile.birthyear,
            )
        except SocialAccountAlreadyLinkedError as link_error:
            logger.warning(
                "social link denied: provider=%s user_id=%s reason=already_linked_elsewhere",
                provider,
                state_entry.link_user_id,
            )
            return _frontend_redirect(error=str(link_error))

        token = jwt_service.create_access_token(user.id, provider, profile.nickname)
        await session_store.set_active_token(token)
        logger.info(
            "social link success: provider=%s user_id=%s newly_linked=%s", provider, user.id, newly_linked
        )
        return _frontend_redirect(
            social=SOCIAL_CODES[provider],
            linked=True,
            alreadyLinked=not newly_linked,
            token=token,
        )

    try:
        user, is_new = await user_store.get_or_create_user(
            db,
            provider=provider,
            provider_user_id=profile.provider_user_id,
            nickname=profile.nickname,
            email=profile.email,
            profile_image_url=profile.profile_image_url,
            gender=profile.gender,
            birthday=profile.birthday,
            birthyear=profile.birthyear,
        )
    except user_store.DuplicateEmailError as dup_error:
        logger.warning(
            "social login denied: provider=%s reason=duplicate_email existing_providers=%s",
            provider,
            dup_error.existing_providers,
        )
        existing_label = ", ".join(dup_error.existing_providers)
        return _frontend_redirect(
            error=f"이미 {existing_label} 계정으로 가입되어 있어요. 해당 계정으로 로그인해주세요."
        )

    token = jwt_service.create_access_token(user.id, provider, profile.nickname)
    await session_store.set_active_token(token)
    user_id = user.id  # 커밋된 ORM 객체 — 실패 시 로그에서 다시 접근하면 lazy reload를 시도한다.
    logger.info("social login success: provider=%s user_id=%s is_new=%s", provider, user_id, is_new)

    try:
        await enqueue_activity(
            db,
            event_type="user.auth.login_succeeded",
            user_id=user_id,
            producer="login-service",
            properties={"method": provider},
        )
    except Exception:
        # 활동 로그 실패로 로그인 자체를 막지 않는다 — analytics는 best-effort.
        # 실패한 커밋은 세션을 rollback-필요 상태로 만드므로, 로그에서 ORM 속성을
        # 다시 읽으면(예: user.id) 또 실패한다 — 위에서 미리 뽑아둔 순수 값만 쓴다.
        await db.rollback()
        logger.exception("activity event enqueue failed: event_type=user.auth.login_succeeded user_id=%s", user_id)

    return _frontend_redirect(
        social=SOCIAL_CODES[provider],
        isNewUser=is_new,
        token=token,
        email=user.email,
        birthday=profile.birthday,
    )
