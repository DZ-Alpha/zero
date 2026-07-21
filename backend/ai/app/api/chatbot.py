import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from app.context.provider import UserContextProvider
from app.handlers.base import HandlerInput
from app.handlers.general_qa import GeneralQAHandler
from app.core.security import get_current_user_from_token
from app.router.dispatcher import Dispatcher
from app.router.intent import IntentClassifier
from app.schemas import ChatbotRequest, ChatbotResponse, Intent, UserContext

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
    qa_handler: GeneralQAHandler | None = None


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


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chatbot/stream")
async def chatbot_stream(
    payload: ChatbotRequest,
    response: Response,
    deps: Dependencies = Depends(get_dependencies),
) -> StreamingResponse:
    # JWT 검증은 스트림 시작 전(실패 시 401을 일반 응답으로).
    if payload.usr:
        identity = get_current_user_from_token(payload.usr, response)
        logger.info("stream request: user_id=%s msg=%r", identity.user_id, payload.msg)
        context = await deps.provider.load(payload.usr)
    else:
        logger.info("stream request(anonymous): msg=%r", payload.msg)
        context = _ANONYMOUS_CONTEXT

    intent = await deps.classifier.classify(msg=payload.msg, has_image=bool(payload.img))
    data = HandlerInput(msg=payload.msg, img=payload.img, template=payload.template, context=context)

    async def events() -> AsyncIterator[str]:
        try:
            if intent is Intent.GENERAL_QA and deps.qa_handler is not None:
                async for delta in deps.qa_handler.handle_stream(data):
                    yield _sse({"delta": delta})
            else:
                # stub 등 비스트리밍 의도는 한 번에 보낸다.
                result = await deps.dispatcher.dispatch(intent, data)
                yield _sse({"delta": result.msg})
        except Exception:
            logger.exception("stream error")
            yield _sse({"error": "일시적인 오류가 발생했습니다.", "state": "error"})
            return
        yield _sse({
            "done": True, "cs-partner": CS_PARTNER,
            "time": datetime.now(timezone.utc).isoformat(), "is-img": False,
        })

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
