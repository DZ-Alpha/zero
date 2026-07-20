from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.schemas import UserContext


class HandlerInput(BaseModel):
    msg: str | None
    img: str | None
    template: str | None
    context: UserContext


class HandlerResult(BaseModel):
    msg: str
    is_img: bool = False


class FeatureHandler(ABC):
    """의도별 기능 핸들러 계약. 지금은 general_qa만 실구현, 나머지는 stub."""

    @abstractmethod
    async def handle(self, data: HandlerInput) -> HandlerResult:
        ...
