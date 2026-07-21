import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from app.context.provider import UserContextProvider
from app.handlers.base import HandlerInput
from app.handlers.general_qa import GeneralQAHandler
from app.core.security import get_current_user_from_token
from app.memory.conversation_store import ConversationStore
from app.memory.session_key import resolve_session_key
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
    store: ConversationStore | None = None


def get_dependencies() -> Dependencies:
    return _DEPENDENCIES


_DEPENDENCIES: Dependencies | None = None


def set_dependencies(deps: Dependencies) -> None:
    global _DEPENDENCIES
    _DEPENDENCIES = deps


async def _load_history(store, session_key):
    if store is None:
        return []
    return await store.load(session_key, turns=6)


@router.post("/chatbot", response_model=ChatbotResponse, response_model_by_alias=True)
async def chatbot(
    payload: ChatbotRequest,
    response: Response,
    deps: Dependencies = Depends(get_dependencies),
) -> ChatbotResponse:
    if payload.usr:
        identity = get_current_user_from_token(payload.usr, response)
        user_id = identity.user_id
        logger.info("chatbot request: user_id=%s msg=%r has_img=%s",
                    user_id, payload.msg, bool(payload.img))
        context = await deps.provider.load(payload.usr)
    else:
        user_id = None
        logger.info("chatbot request(anonymous): msg=%r has_img=%s", payload.msg, bool(payload.img))
        context = _ANONYMOUS_CONTEXT

    session_key = resolve_session_key(user_id, payload.session_id)
    history = await _load_history(deps.store, session_key)

    intent = await deps.classifier.classify(msg=payload.msg, has_image=bool(payload.img))
    data = HandlerInput(msg=payload.msg, img=payload.img, template=payload.template, context=context)

    if intent is Intent.GENERAL_QA and deps.qa_handler is not None:
        result = await deps.qa_handler.handle(data, history=history)
    else:
        result = await deps.dispatcher.dispatch(intent, data)

    if deps.store is not None and payload.msg:
        await deps.store.append(session_key, payload.msg, result.msg)

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
    if payload.usr:
        identity = get_current_user_from_token(payload.usr, response)
        user_id = identity.user_id
        logger.info("stream request: user_id=%s msg=%r", user_id, payload.msg)
        context = await deps.provider.load(payload.usr)
    else:
        user_id = None
        logger.info("stream request(anonymous): msg=%r", payload.msg)
        context = _ANONYMOUS_CONTEXT

    session_key = resolve_session_key(user_id, payload.session_id)
    history = await _load_history(deps.store, session_key)

    intent = await deps.classifier.classify(msg=payload.msg, has_image=bool(payload.img))
    data = HandlerInput(msg=payload.msg, img=payload.img, template=payload.template, context=context)

    async def events() -> AsyncIterator[str]:
        answer_parts: list[str] = []
        try:
            if intent is Intent.GENERAL_QA and deps.qa_handler is not None:
                async for delta in deps.qa_handler.handle_stream(data, history=history):
                    answer_parts.append(delta)
                    yield _sse({"delta": delta})
            else:
                result = await deps.dispatcher.dispatch(intent, data)
                answer_parts.append(result.msg)
                yield _sse({"delta": result.msg})
        except Exception:
            logger.exception("stream error")
            yield _sse({"error": "일시적인 오류가 발생했습니다.", "state": "error"})
            return
        # 답변이 끝난 뒤에만 저장(반쪽 대화 방지). Redis 장애는 store가 삼킨다.
        if deps.store is not None and payload.msg:
            await deps.store.append(session_key, payload.msg, "".join(answer_parts))
        yield _sse({
            "done": True, "cs-partner": CS_PARTNER,
            "time": datetime.now(timezone.utc).isoformat(), "is-img": False,
        })

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/chatbot/history")
async def chatbot_history(
    response: Response,
    usr: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    deps: Dependencies = Depends(get_dependencies),
) -> dict:
    # 로그인이면 usr(JWT)로 user_id, 아니면 session_id로 게스트 키.
    user_id = None
    if usr:
        identity = get_current_user_from_token(usr, response)
        user_id = identity.user_id
    session_key = resolve_session_key(user_id, session_id)
    messages = []
    if deps.store is not None:
        messages = await deps.store.load_all(session_key)
    return {"messages": messages}
