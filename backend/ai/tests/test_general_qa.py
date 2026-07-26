from app.handlers.base import HandlerInput
from app.handlers.general_qa import GeneralQAHandler, render_user_context_block, strip_chat_markdown
from app.rag.retriever import RagChunk, Retriever
from app.schemas import UserContext


def test_strip_chat_markdown_removes_bold_and_headings():
    raw = "## 제목\n**당류**는 20g이고 *중요*합니다.\n\n\n\n끝."
    out = strip_chat_markdown(raw)
    assert "**" not in out
    assert "##" not in out
    assert "제목" in out and "당류" in out and "중요" in out
    assert "\n\n\n" not in out  # 과한 줄바꿈 정리


class _FakeLLM:
    def __init__(self):
        self.last_user = None
        self.last_system = None

    async def complete(self, system: str, messages: list[dict]) -> str:
        self.last_system = system
        self.last_user = messages[-1]["text"]
        return "대화체 답변입니다"


class _FakeRetriever(Retriever):
    async def search_docs(self, query: str, k: int = 4):
        return [RagChunk(text="식약처: 무당류 100g당 0.5g 미만", source="식약처", score=0.9)]

    async def search_products(self, query: str, k: int = 4):
        return [RagChunk(text="초코바 당류 20g", source="상품DB", score=0.8)]


def _ctx(consent: bool, sugar):
    return UserContext(user_id=1, logged_in=True, interests=["저당"], has_allergy=True,
                       consent=consent, daily_sugar_target_g=sugar, daily_calorie_target=1900.0 if consent else None)


def test_context_block_with_targets_mentions_goal():
    block = render_user_context_block(_ctx(True, 48.0))
    assert "48" in block
    assert "알레르기" in block  # has_allergy=True 반영


def test_context_block_without_consent_uses_general_baseline():
    block = render_user_context_block(_ctx(False, None))
    # 개인 목표값을 지어내지 않는다 — 숫자 목표가 없어야 함
    assert "일반" in block


def test_context_block_calculates_from_body_info_when_no_target():
    # 저장 목표값은 없지만 신체정보가 다 있으면 코드로 계산해 개인화한다(설계 §5.2 2단계).
    ctx = UserContext(user_id=1, logged_in=True, interests=[], has_allergy=False,
                      consent=False, daily_sugar_target_g=None, daily_calorie_target=None,
                      gender="남성", age=27, height_cm=180, weight_kg=70,
                      activity_level="주로 앉아서 생활해요")
    block = render_user_context_block(ctx)
    assert "2090" in block  # 계산된 칼로리
    assert "추정" in block   # 추정치임을 밝힘


async def test_handler_injects_rag_and_context_into_prompt():
    llm = _FakeLLM()
    handler = GeneralQAHandler(llm=llm, retriever=_FakeRetriever())
    data = HandlerInput(msg="이 초코바 먹어도 돼?", img=None, template=None, context=_ctx(True, 48.0))
    result = await handler.handle(data)
    assert result.msg == "대화체 답변입니다"
    assert result.is_img is False
    # ①번은 RAG 문서 + 사용자맥락을 주입한다(상품검색은 기능② 영역이라 여기선 미사용).
    assert "0.5g 미만" in llm.last_user
    assert "48" in llm.last_user


async def test_handler_does_not_call_search_products():
    # ①번 경로는 search_products를 호출하지 않는다(상품벡터 테이블 스키마 상이).
    called = {"products": False}

    class _R(_FakeRetriever):
        async def search_products(self, query: str, k: int = 4):
            called["products"] = True
            return []

    handler = GeneralQAHandler(llm=_FakeLLM(), retriever=_R())
    data = HandlerInput(msg="탄수화물이 뭐야?", img=None, template=None, context=_ctx(False, None))
    await handler.handle(data)
    assert called["products"] is False


async def test_handler_uses_system_prompt():
    llm = _FakeLLM()
    handler = GeneralQAHandler(llm=llm, retriever=_FakeRetriever())
    data = HandlerInput(msg="탄수화물이 뭐야?", img=None, template=None, context=_ctx(False, None))
    await handler.handle(data)
    assert "당당봇" in llm.last_system
