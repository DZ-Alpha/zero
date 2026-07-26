import logging
from datetime import date
from typing import Annotated

import jwt as pyjwt
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SOCIAL_CODES
from app.core.database import get_db
from app.models.admin_account import AdminAccount
from app.models.social_account import SocialAccount
from app.models.user import User
from app.services import jwt_service, user_store
from app.services.user_store import DuplicateEmailError, LastSocialAccountError, SocialAccountNotFoundError

logger = logging.getLogger("app.user")

router = APIRouter(prefix="/user")


def _calculate_age(birthday: date | None) -> int | None:
    if birthday is None:
        return None
    today = date.today()
    return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))


def _resolve_token(usr: str | None, authorization: str | None) -> str:
    """PRODUCTION_HANDOFF.md P0-4 — usr 쿼리파라미터/바디와 Authorization: Bearer
    헤더를 둘 다 받는다(헤더 우선). 기존 usr 방식 호출은 그대로 동작한다."""
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    if usr:
        return usr
    raise HTTPException(status_code=401, detail="인증 정보가 없습니다.")


def _decode_user_id_or_401(token: str, response: Response) -> int:
    try:
        payload = jwt_service.decode_payload(token)
    except pyjwt.InvalidTokenError as error:
        logger.warning("user request denied: reason=invalid_token")
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.") from error

    # 슬라이딩 세션 — 이 토큰으로 뭔가 하나 성공할 때마다 만료시각을 연장한
    # 새 토큰을 헤더로 내려준다. 프론트는 이 헤더가 있으면 저장된 토큰을 교체한다.
    response.headers["X-Refreshed-Token"] = jwt_service.refresh_token(payload)
    return int(payload["sub"])


class FirstSetRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    usr: str | None = None
    nickname: str | None = None
    email: str | None = None
    favorite_category: Annotated[list[str] | None, Field(alias="favoriteCategory")] = None
    is_allergic: Annotated[bool | None, Field(alias="isAllergic")] = None
    optional_agree: Annotated[bool | None, Field(alias="optionalAgree")] = None
    tall: int | None = None
    weight: float | None = None
    birthday: date | None = None


@router.post("/firstset")
async def first_set(
    payload: FirstSetRequest,
    response: Response,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    user_id = _decode_user_id_or_401(_resolve_token(payload.usr, authorization), response)

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    if payload.nickname is not None:
        stripped = payload.nickname.strip()
        if stripped:
            user.display_name = stripped
    if payload.email is not None:
        stripped_email = payload.email.strip()
        if stripped_email:
            if "@" not in stripped_email:
                raise HTTPException(status_code=422, detail="올바른 이메일 형식이 아니에요.")
            try:
                await user_store.ensure_email_available(db, user_id, stripped_email)
            except DuplicateEmailError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            user.email = stripped_email
    if payload.favorite_category is not None:
        user.favorite_categories = payload.favorite_category
    if payload.is_allergic is not None:
        user.is_allergic = payload.is_allergic
    if payload.optional_agree is not None:
        user.optional_agree = payload.optional_agree
    if payload.tall is not None:
        user.tall = payload.tall
    if payload.weight is not None:
        user.weight = payload.weight
    if payload.birthday is not None:
        user.birthday = payload.birthday

    await db.commit()

    return {"status": "SUCCESS"}


@router.get("/mypage")
async def get_mypage(
    response: Response,
    usr: str | None = None,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user_id = _decode_user_id_or_401(_resolve_token(usr, authorization), response)

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    stmt = select(SocialAccount).where(SocialAccount.user_id == user_id)
    social_accounts = (await db.execute(stmt)).scalars().all()
    enabled_sns = [SOCIAL_CODES[account.provider] for account in social_accounts]

    admin_account = await db.scalar(select(AdminAccount).where(AdminAccount.user_id == user_id))
    if admin_account is not None:
        enabled_sns.append(SOCIAL_CODES["admin"])

    return {
        "enabledSns": enabled_sns,
        "nickname": user.display_name or (social_accounts[0].nickname if social_accounts else None),
        "email": user.email,
        "optionalAgree": user.optional_agree,
        "favorite": user.favorite_categories,
        "healthStat": {
            "optionalAgree": user.optional_agree,
            "allergic": user.is_allergic,
            "tall": user.tall,
            "weight": float(user.weight) if user.weight is not None else None,
            "age": _calculate_age(user.birthday),
        },
    }


@router.delete("/social/{provider}")
async def unlink_social(
    provider: str,
    response: Response,
    usr: str | None = None,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user_id = _decode_user_id_or_401(_resolve_token(usr, authorization), response)

    try:
        remaining = await user_store.unlink_social_account(db, user_id=user_id, provider=provider)
    except SocialAccountNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except LastSocialAccountError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return {"status": "SUCCESS", "enabledSns": [SOCIAL_CODES[p] for p in remaining]}


@router.delete("/mypage")
async def leave(
    exituser: str,
    response: Response,
    usr: str | None = None,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if exituser != "EXIT":
        raise HTTPException(status_code=400, detail="exituser=EXIT 파라미터로 탈퇴 의사를 명시적으로 확인해야 합니다.")

    # 탈퇴 처리 자체엔 갱신 토큰이 의미 없지만(계정이 곧 사라짐), 검증 로직은
    # 통일해서 쓴다 — 헤더는 그냥 무시돼도 무해하다.
    user_id = _decode_user_id_or_401(_resolve_token(usr, authorization), response)
    await user_store.delete_user(db, user_id)

    return {"status": "SUCCESS"}
