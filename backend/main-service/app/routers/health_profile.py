from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_from_token, resolve_token
from app.models.user_health_profile import UserHealthProfile
from app.services.health_profile_store import (
    HealthDataConsentRequiredError,
    get_health_profile,
    upsert_health_profile,
)

router = APIRouter(prefix="/home")


class HealthProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    usr: str | None = None
    consent: bool = False
    birth_year: Annotated[int | None, Field(alias="birthYear")] = None
    gender: str | None = None
    height_cm: Annotated[float | None, Field(alias="heightCm")] = None
    weight_kg: Annotated[float | None, Field(alias="weightKg")] = None
    activity_level: Annotated[str | None, Field(alias="activityLevel")] = None
    health_goal: Annotated[str | None, Field(alias="healthGoal")] = None
    daily_calorie_target: Annotated[float | None, Field(alias="dailyCalorieTarget")] = None
    daily_sugar_target_g: Annotated[float | None, Field(alias="dailySugarTargetG")] = None

    # 2026-07-30 QA 리포트: 비정상 값(height_cm=18900 등)이 그대로 넘어오면
    # height_cm/weight_kg 컬럼이 Numeric(5,2)라 DB 오버플로로 500이 났다
    # (겉으론 "일시적인 오류가 발생했습니다"만 보여 원인이 가려짐). 여기서
    # 먼저 422로 막아 컬럼 한도(999.99)와 무관하게 애초에 말이 되는 값만
    # 통과시킨다. 하루 목표 상하한도 검증 없이 그대로 저장되던 문제(5710kcal,
    # 168g)도 같이 막는다.
    @field_validator("height_cm")
    @classmethod
    def _validate_height(cls, value: float | None) -> float | None:
        if value is not None and not (50 <= value <= 250):
            raise ValueError("키는 50~250cm 사이여야 해요.")
        return value

    @field_validator("weight_kg")
    @classmethod
    def _validate_weight(cls, value: float | None) -> float | None:
        if value is not None and not (20 <= value <= 300):
            raise ValueError("몸무게는 20~300kg 사이여야 해요.")
        return value

    @field_validator("daily_calorie_target")
    @classmethod
    def _validate_calorie_target(cls, value: float | None) -> float | None:
        if value is not None and not (800 <= value <= 6000):
            raise ValueError("하루 칼로리 목표는 800~6000kcal 사이여야 해요.")
        return value

    @field_validator("daily_sugar_target_g")
    @classmethod
    def _validate_sugar_target(cls, value: float | None) -> float | None:
        if value is not None and not (5 <= value <= 300):
            raise ValueError("하루 당류 목표는 5~300g 사이여야 해요.")
        return value


def _serialize(profile: UserHealthProfile | None) -> dict[str, object]:
    if profile is None:
        return {
            "birthYear": None,
            "gender": None,
            "heightCm": None,
            "weightKg": None,
            "activityLevel": None,
            "healthGoal": None,
            "dailyCalorieTarget": None,
            "dailySugarTargetG": None,
            "targetSource": None,
            "consent": False,
        }
    return {
        "birthYear": profile.birth_year,
        "gender": profile.gender,
        "heightCm": float(profile.height_cm) if profile.height_cm is not None else None,
        "weightKg": float(profile.weight_kg) if profile.weight_kg is not None else None,
        "activityLevel": profile.activity_level,
        "healthGoal": profile.health_goal,
        "dailyCalorieTarget": float(profile.daily_calorie_target) if profile.daily_calorie_target is not None else None,
        "dailySugarTargetG": float(profile.daily_sugar_target_g) if profile.daily_sugar_target_g is not None else None,
        "targetSource": profile.target_source,
        "consent": profile.health_data_consent_at is not None,
    }


@router.get("/health-profile")
async def read_health_profile(
    response: Response,
    usr: str | None = None,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = get_current_user_from_token(resolve_token(usr, authorization), response)
    profile = await get_health_profile(db, user.user_id)
    return _serialize(profile)


@router.put("/health-profile")
async def update_health_profile(
    payload: HealthProfileUpdateRequest,
    response: Response,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = get_current_user_from_token(resolve_token(payload.usr, authorization), response)
    try:
        profile = await upsert_health_profile(
            db,
            user.user_id,
            consent=payload.consent,
            birth_year=payload.birth_year,
            gender=payload.gender,
            height_cm=payload.height_cm,
            weight_kg=payload.weight_kg,
            activity_level=payload.activity_level,
            health_goal=payload.health_goal,
            daily_calorie_target=payload.daily_calorie_target,
            daily_sugar_target_g=payload.daily_sugar_target_g,
        )
    except HealthDataConsentRequiredError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return {"status": "SUCCESS", **_serialize(profile)}
