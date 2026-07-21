from app.handlers.base import HandlerInput
from app.handlers.general_qa import GeneralQAHandler
from app.rag.retriever import RagChunk, Retriever
from app.schemas import UserContext


class _StreamLLM:
    def __init__(self):
        self.last_user = None
        self.last_system = None

    async def complete(self, system, messages):
        return "x"

    async def complete_stream(self, system, messages):
        self.last_system = system
        self.last_user = messages[-1]["text"]
        for part in ["탄수화물은", " 에너지원", "이에요"]:
            yield part


class _FakeRetriever(Retriever):
    async def search_docs(self, query, k=4):
        return [RagChunk(text="식약처: 무당류 100g당 0.5g 미만", source="식약처", score=0.9)]

    async def search_products(self, query, k=4):
        return []


def _ctx():
    return UserContext(user_id=1, logged_in=True, interests=["저당"], has_allergy=False,
                       consent=True, daily_sugar_target_g=48.0, daily_calorie_target=1900.0)


async def test_handle_stream_yields_deltas():
    llm = _StreamLLM()
    h = GeneralQAHandler(llm=llm, retriever=_FakeRetriever())
    data = HandlerInput(msg="탄수화물이 뭐야?", img=None, template=None, context=_ctx())
    out = []
    async for d in h.handle_stream(data):
        out.append(d)
    assert out == ["탄수화물은", " 에너지원", "이에요"]


async def test_handle_stream_injects_rag_and_context():
    llm = _StreamLLM()
    h = GeneralQAHandler(llm=llm, retriever=_FakeRetriever())
    data = HandlerInput(msg="이 초코바?", img=None, template=None, context=_ctx())
    async for _ in h.handle_stream(data):
        pass
    assert "0.5g 미만" in llm.last_user   # RAG 근거
    assert "48" in llm.last_user           # 개인 목표
    assert "당당봇" in llm.last_system      # 시스템 프롬프트
