from datetime import date
from typing import Annotated

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SOCIAL_CODES
from app.core.database import get_db
from app.models.social_account import SocialAccount
from app.models.user import User
from app.services import jwt_service, user_store
from app.services.user_store import LastSocialAccountError, SocialAccountNotFoundError

router = APIRouter(prefix="/user")


def _calculate_age(birthday: date | None) -> int | None:
    if birthday is None:
        return None
    today = date.today()
    return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))


def _decode_user_id_or_401(token: str) -> int:
    try:
        return jwt_service.decode_user_id(token)
    except pyjwt.InvalidTokenError as error:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.") from error


class FirstSetRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    usr: str
    favorite_category: Annotated[list[str] | None, Field(alias="favoriteCategory")] = None
    is_allergic: Annotated[bool | None, Field(alias="isAllergic")] = None
    optional_agree: Annotated[bool | None, Field(alias="optionalAgree")] = None
    tall: int | None = None
    weight: float | None = None
    birthday: date | None = None


@router.post("/firstset")
async def first_set(payload: FirstSetRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    user_id = _decode_user_id_or_401(payload.usr)

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

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
async def get_mypage(usr: str, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    user_id = _decode_user_id_or_401(usr)

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    stmt = select(SocialAccount).where(SocialAccount.user_id == user_id)
    social_accounts = (await db.execute(stmt)).scalars().all()
    enabled_sns = [SOCIAL_CODES[account.provider] for account in social_accounts]

    return {
        "enabledSns": enabled_sns,
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
async def unlink_social(provider: str, usr: str, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    user_id = _decode_user_id_or_401(usr)

    try:
        remaining = await user_store.unlink_social_account(db, user_id=user_id, provider=provider)
    except SocialAccountNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except LastSocialAccountError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return {"status": "SUCCESS", "enabledSns": [SOCIAL_CODES[p] for p in remaining]}


@router.delete("/mypage")
async def leave(usr: str, exituser: str, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    if exituser != "EXIT":
        raise HTTPException(status_code=400, detail="exituser=EXIT 파라미터로 탈퇴 의사를 명시적으로 확인해야 합니다.")

    user_id = _decode_user_id_or_401(usr)
    await user_store.delete_user(db, user_id)

    return {"status": "SUCCESS"}
