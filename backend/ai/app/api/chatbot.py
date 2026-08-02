import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Response
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
from app.services.chat_photo_storage import presign_chat_photo_url

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

    image_key = getattr(result, "image_key", None)
    if deps.store is not None and (payload.msg or image_key):
        await deps.store.append(session_key, payload.msg or "", result.msg, image_key=image_key)

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
        image_key: str | None = None
        try:
            if intent is Intent.GENERAL_QA and deps.qa_handler is not None:
                async for delta in deps.qa_handler.handle_stream(data, history=history):
                    answer_parts.append(delta)
                    yield _sse({"delta": delta})
            else:
                # 사진분석·stub 등 비스트리밍 의도는 답변이 한 번에 완성된다.
                # 글자 단위로 흘려 GENERAL_QA와 같은 타이핑 체감을 준다(가짜 스트리밍).
                result = await deps.dispatcher.dispatch(intent, data)
                image_key = result.image_key
                answer_parts.append(result.msg)
                for ch in result.msg:
                    yield _sse({"delta": ch})
                    await asyncio.sleep(0.015)
        except Exception:
            logger.exception("stream error")
            yield _sse({"error": "일시적인 오류가 발생했습니다.", "state": "error"})
            return
        except BaseException:
            # 클라이언트가 스트림 도중 연결을 끊으면(채팅창을 닫는 등) 이 지점이
            # asyncio.CancelledError로 취소된다 - Python 3.8+에서 CancelledError는
            # Exception이 아니라 BaseException 계열이라 위 except Exception에 안
            # 걸린다. 그대로 두면 답변을 이미 다 만들었어도 아래 저장 줄까지 못
            # 가서 대화가 통째로 사라진다("채팅 닫으면 바로 지워지는 문제"의 원인).
            # 취소 자체는 삼키지 않고 다시 던지되, 그 전에 지금까지 만든 답변만은
            # best-effort로 저장한다.
            if deps.store is not None and (payload.msg or image_key) and answer_parts:
                try:
                    await asyncio.shield(
                        deps.store.append(session_key, payload.msg or "", "".join(answer_parts), image_key=image_key)
                    )
                except Exception:
                    logger.warning("cancel-time conversation save failed (key=%s)", session_key, exc_info=True)
            raise
        # 답변이 끝난 뒤에만 저장(반쪽 대화 방지). Redis 장애는 store가 삼킨다.
        # 사진 턴(PRODUCT_ANALYSIS)은 result.image_key 사용.
        if deps.store is not None and (payload.msg or image_key):
            await deps.store.append(session_key, payload.msg or "", "".join(answer_parts), image_key=image_key)
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
    authorization: str | None = Header(None),
    usr: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    deps: Dependencies = Depends(get_dependencies),
) -> dict:
    # 2026-08-02 QA 리포트 — usr을 쿼리스트링으로 받으면 JWT가 Istio/Loki 로그에
    # 그대로 남는다. Authorization: Bearer 헤더를 우선 사용하고, usr 쿼리는 과거
    # 프론트 호출과의 호환을 위해서만 폴백으로 남긴다(다음 정리 대상).
    # 로그인이면 토큰으로 user_id, 아니면 session_id로 게스트 키.
    user_id = None
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif usr:
        token = usr
    if token:
        identity = get_current_user_from_token(token, response)
        user_id = identity.user_id
    session_key = resolve_session_key(user_id, session_id)
    messages = []
    if deps.store is not None:
        raw = await deps.store.load_all(session_key)
        for m in raw:
            item = {"role": m["role"], "text": m["text"]}
            key = m.get("image_key")
            if key:
                url = presign_chat_photo_url(key)
                if url:
                    item["imageUrl"] = url
            messages.append(item)
    return {"messages": messages}
