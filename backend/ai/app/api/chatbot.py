import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict

from app.context.provider import UserContextProvider
from app.handlers.base import HandlerInput
from app.core.security import get_current_user_from_token
from app.router.dispatcher import Dispatcher
from app.router.intent import IntentClassifier
from app.schemas import ChatbotRequest, ChatbotResponse, UserContext

_ANONYMOUS_CONTEXT = UserContext(
    user_id=0, logged_in=False, interests=[], has_allergy=False,
    consent=False, daily_sugar_target_g=None, daily_calorie_target=None,
)

logger = logging.getLogger("ai_chatbot")

router = APIRouter(prefix="/ai")

CS_PARTNER = "당당봇"


class Dependencies(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    provider: UserContextProvider
    classifier: IntentClassifier
    dispatcher: Dispatcher


def get_dependencies() -> Dependencies:
    # 실제 조립은 main.py의 build_dependencies가 앱 시작 시 세팅한다.
    return _DEPENDENCIES


_DEPENDENCIES: Dependencies | None = None


def set_dependencies(deps: Dependencies) -> None:
    global _DEPENDENCIES
    _DEPENDENCIES = deps


@router.post("/chatbot", response_model=ChatbotResponse, response_model_by_alias=True)
async def chatbot(
    payload: ChatbotRequest,
    response: Response,
    deps: Dependencies = Depends(get_dependencies),
) -> ChatbotResponse:
    # usr(JWT) 있으면 검증 후 개인화, 없으면 익명(일반 기준) 답변.
    if payload.usr:
        # JWT 검증 (실패 시 401) — 성공 시 X-Refreshed-Token 부여
        identity = get_current_user_from_token(payload.usr, response)
        logger.info("chatbot request: user_id=%s msg=%r has_img=%s",
                    identity.user_id, payload.msg, bool(payload.img))
        context = await deps.provider.load(payload.usr)
    else:
        logger.info("chatbot request(anonymous): msg=%r has_img=%s", payload.msg, bool(payload.img))
        context = _ANONYMOUS_CONTEXT
    intent = await deps.classifier.classify(msg=payload.msg, has_image=bool(payload.img))
    result = await deps.dispatcher.dispatch(
        intent,
        HandlerInput(msg=payload.msg, img=payload.img, template=payload.template, context=context),
    )
    return ChatbotResponse(
        cs_partner=CS_PARTNER,
        time=datetime.now(timezone.utc).isoformat(),
        msg=result.msg,
        is_img=result.is_img,
    )
