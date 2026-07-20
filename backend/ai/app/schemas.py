from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Intent(str, Enum):
    GENERAL_QA = "general_qa"
    PRODUCT_ANALYSIS = "product_analysis"
    RECOMMEND = "recommend"
    DIET_PHOTO = "diet_photo"
    RECIPE_SUBSTITUTE = "recipe_substitute"
    ADMIN_ANALYTICS = "admin_analytics"


class ChatbotRequest(BaseModel):
    # 비로그인 사용자도 일반 지식질문은 쓸 수 있게 usr은 옵셔널.
    # 토큰이 있으면 개인화, 없으면 익명(일반 기준) 답변.
    usr: str | None = None
    msg: str | None = None
    template: str | None = None
    img: str | None = None

    @model_validator(mode="after")
    def _require_msg_or_img(self) -> "ChatbotRequest":
        if not self.msg and not self.img:
            raise ValueError("msg 또는 img 중 하나는 필요합니다.")
        return self


class ChatbotResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cs_partner: str = Field(serialization_alias="cs-partner")
    time: str
    msg: str
    is_img: bool = Field(serialization_alias="is-img")


class UserContext(BaseModel):
    user_id: int
    logged_in: bool
    interests: list[str]
    has_allergy: bool
    consent: bool
    daily_sugar_target_g: float | None
    daily_calorie_target: float | None
    # 신체정보 — 저장된 목표값이 없을 때 코드로 목표를 계산하는 데 쓴다.
    gender: str | None = None
    age: int | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    activity_level: str | None = None
