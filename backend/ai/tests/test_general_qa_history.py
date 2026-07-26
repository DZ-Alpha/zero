import pytest

from app.handlers.base import HandlerInput
from app.handlers.general_qa import GeneralQAHandler
from app.rag.retriever import Retriever
from app.schemas import UserContext


class _CaptureLLM:
    def __init__(self):
        self.messages = None

    async def complete(self, system, messages):
        self.messages = messages
        return "답변"

    async def complete_stream(self, system, messages):
        self.messages = messages
        for p in ["답", "변"]:
            yield p


class _EmptyRetriever(Retriever):
    async def search_docs(self, query, k=4):
        return []

    async def search_products(self, query, k=4):
        return []


def _ctx():
    return UserContext(user_id=0, logged_in=False, interests=[], has_allergy=False,
                       consent=False, daily_sugar_target_g=None, daily_calorie_target=None)


def _data(msg):
    return HandlerInput(msg=msg, img=None, template=None, context=_ctx())


async def test_handle_prepends_history_before_current():
    llm = _CaptureLLM()
    h = GeneralQAHandler(llm=llm, retriever=_EmptyRetriever())
    history = [
        {"role": "user", "text": "나 알레르기 있어"},
        {"role": "assistant", "text": "어떤 성분요?"},
    ]
    await h.handle(_data("땅콩"), history=history)
    # 과거 history는 원문 그대로 앞에 붙고, 현재 턴만 RAG·개인화가 섞인 프롬프트가 된다.
    assert llm.messages[:2] == history
    assert len(llm.messages) == 3
    assert llm.messages[2]["role"] == "user"
    assert "땅콩" in llm.messages[2]["text"]


async def test_handle_without_history_is_single_message():
    llm = _CaptureLLM()
    h = GeneralQAHandler(llm=llm, retriever=_EmptyRetriever())
    await h.handle(_data("당류가 뭐야"))
    assert len(llm.messages) == 1
    assert llm.messages[0]["role"] == "user"
    assert "당류가 뭐야" in llm.messages[0]["text"]


async def test_stream_prepends_history():
    llm = _CaptureLLM()
    h = GeneralQAHandler(llm=llm, retriever=_EmptyRetriever())
    history = [{"role": "user", "text": "안녕"}, {"role": "assistant", "text": "네"}]
    chunks = [c async for c in h.handle_stream(_data("땅콩"), history=history)]
    assert "".join(chunks) == "답변"
    assert llm.messages[:2] == history
    assert len(llm.messages) == 3
    assert llm.messages[2]["role"] == "user"
    assert "땅콩" in llm.messages[2]["text"]
