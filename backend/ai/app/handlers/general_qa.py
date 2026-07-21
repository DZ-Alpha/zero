import re

from app.core.targets import calculate_targets
from app.handlers.base import FeatureHandler, HandlerInput, HandlerResult
from app.llm.bedrock_client import LLMClient
from app.llm.prompts import SYSTEM_PROMPT_QA, build_qa_user_prompt
from app.rag.retriever import Retriever, blocks_to_text
from app.schemas import UserContext

_HEADING = re.compile(r"^#{1,6}\s*", re.MULTILINE)  # 줄 시작의 # 제목
_BOLD = re.compile(r"\*{1,3}(.+?)\*{1,3}", re.DOTALL)  # **볼드**/*이탤릭*
_MULTI_NL = re.compile(r"\n{3,}")


def strip_chat_markdown(text: str) -> str:
    """좁은 채팅창용으로 마크다운을 제거한다. LLM이 프롬프트 규칙을 어겨도
    볼드(**)·제목(#)이 화면에 노출되지 않도록 응답을 후처리한다."""
    text = _HEADING.sub("", text)
    text = _BOLD.sub(r"\1", text)
    text = _MULTI_NL.sub("\n\n", text)
    return text.strip()


def render_user_context_block(ctx: UserContext) -> str:
    if not ctx.logged_in:
        return "로그인하지 않은 사용자입니다. 일반 기준으로 안내하세요."
    lines: list[str] = []
    if ctx.interests:
        lines.append(f"관심사: {', '.join(ctx.interests)}")
    if ctx.has_allergy:
        lines.append("알레르기가 있습니다(구체 성분은 미상 — 원재료 확인 안내 필요).")
    # 개인화 3단계(설계 §5.2): ① 저장된 목표값 → ② 신체정보로 코드 계산 → ③ 일반 기준.
    if ctx.consent and ctx.daily_sugar_target_g is not None:
        lines.append(f"하루 당류 목표: {ctx.daily_sugar_target_g}g")
        if ctx.daily_calorie_target is not None:
            lines.append(f"하루 칼로리 목표: {ctx.daily_calorie_target}kcal")
    else:
        calc = calculate_targets(ctx.gender, ctx.age, ctx.height_cm, ctx.weight_kg, ctx.activity_level)
        if calc is not None:
            cal, sugar = calc
            lines.append(f"신체정보 기반 추정 목표(일반 공식): 하루 칼로리 약 {cal}kcal, 당류 약 {sugar}g. "
                         "이는 추정치이며 저장된 목표가 아님을 밝혀라.")
        else:
            lines.append("개인 하루 목표값이 없습니다. 일반 기준으로 안내하고 개인값을 지어내지 마세요.")
    return "\n".join(lines)


class GeneralQAHandler(FeatureHandler):
    def __init__(self, llm: LLMClient, retriever: Retriever) -> None:
        self._llm = llm
        self._retriever = retriever

    async def handle(self, data: HandlerInput) -> HandlerResult:
        query = data.msg or ""
        # ①번 일반 지식질문은 RAG 문서(식약처/WHO/KDRIs)만 근거로 답한다.
        # 상품 성분 검색은 기능 ②(상품 분석) 영역이라 여기서 호출하지 않는다
        # (상품벡터 테이블 service.product_embeddings는 컬럼 구조가 달라 별도 처리 필요).
        docs = await self._retriever.search_docs(query)
        user_prompt = build_qa_user_prompt(
            msg=query,
            user_context_block=render_user_context_block(data.context),
            rag_block=blocks_to_text(docs),
            product_block="",
        )
        answer = await self._llm.complete(SYSTEM_PROMPT_QA, user_prompt)
        return HandlerResult(msg=strip_chat_markdown(answer), is_img=False)

    async def handle_stream(self, data: HandlerInput):
        # 스트리밍 경로 — 인증·RAG·프롬프트 조립은 handle과 동일, LLM만 스트리밍.
        # 마크다운 후처리는 하지 않는다(프론트가 렌더링).
        query = data.msg or ""
        docs = await self._retriever.search_docs(query)
        user_prompt = build_qa_user_prompt(
            msg=query,
            user_context_block=render_user_context_block(data.context),
            rag_block=blocks_to_text(docs),
            product_block="",
        )
        async for delta in self._llm.complete_stream(SYSTEM_PROMPT_QA, user_prompt):
            yield delta
