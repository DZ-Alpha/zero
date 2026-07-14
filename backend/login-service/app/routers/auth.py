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
from app.services.oauth import kakao, naver
from app.services.oauth.types import OAuthExchangeError
from app.services.user_store import SocialAccountAlreadyLinkedError

router = APIRouter(prefix="/auth")

_PROVIDERS: dict[str, ModuleType] = {"naver": naver, "kakao": kakao}


def _get_provider_module(provider: str) -> ModuleType:
    module = _PROVIDERS.get(provider)
    if module is None:
        raise HTTPException(status_code=404, detail=f"지원하지 않는 로그인 제공자입니다: {provider}")
    return module


def _frontend_redirect(**params: str | bool | None) -> RedirectResponse:
    query_params = {key: str(value) for key, value in params.items() if value is not None}
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?{urlencode(query_params)}")


@router.get("/{provider}/login")
def login(provider: str) -> RedirectResponse:
    module = _get_provider_module(provider)
    state = state_store.create_state()
    return RedirectResponse(module.build_authorize_url(state))


@router.post("/session")
def activate_session(token: str) -> dict[str, str]:
    try:
        jwt_service.decode_user_id(token)
    except pyjwt.InvalidTokenError as error:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.") from error

    session_store.set_active_token(token)
    return {"status": "ok"}


@router.get("/{provider}/link")
def link(provider: str, token: str | None = None) -> RedirectResponse:
    module = _get_provider_module(provider)
    active_token = token or session_store.get_active_token()
    if active_token is None:
        raise HTTPException(status_code=401, detail="연동할 활성 세션 토큰이 없습니다. 먼저 로그인해주세요.")

    try:
        user_id = jwt_service.decode_user_id(active_token)
    except pyjwt.InvalidTokenError as error:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.") from error

    state = state_store.create_state(link_user_id=user_id)
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

    state_entry = state_store.verify_and_consume_state(state)
    if state_entry is None:
        return _frontend_redirect(error="state 값이 유효하지 않거나 만료되었습니다.")

    if error is not None:
        return _frontend_redirect(error=f"{provider} 로그인이 취소되었거나 실패했습니다: {error_description or error}")

    if code is None:
        return _frontend_redirect(error="인증 코드가 전달되지 않았습니다.")

    try:
        access_token = await module.exchange_code_for_token(code, state)
        profile = await module.fetch_profile(access_token)
    except (httpx.HTTPError, OAuthExchangeError) as exchange_error:
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
            return _frontend_redirect(error=str(link_error))

        token = jwt_service.create_access_token(user.id, provider, profile.nickname)
        session_store.set_active_token(token)
        return _frontend_redirect(
            social=SOCIAL_CODES[provider],
            linked=True,
            alreadyLinked=not newly_linked,
            token=token,
        )

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
    token = jwt_service.create_access_token(user.id, provider, profile.nickname)
    session_store.set_active_token(token)

    return _frontend_redirect(
        social=SOCIAL_CODES[provider],
        isNewUser=is_new,
        token=token,
        email=user.email,
        birthday=profile.birthday,
    )
