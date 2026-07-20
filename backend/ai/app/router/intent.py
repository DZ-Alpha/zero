from collections.abc import Awaitable, Callable

from app.schemas import Intent

LlmClassify = Callable[[str], Awaitable[Intent]]


class IntentClassifier:
    """이미지 첨부는 규칙으로 즉시 판정, 텍스트 의도는 LLM에 위임."""

    def __init__(self, llm_classify: LlmClassify) -> None:
        self._llm_classify = llm_classify

    async def classify(self, msg: str | None, has_image: bool) -> Intent:
        if has_image:
            return Intent.PRODUCT_ANALYSIS
        if not msg:
            return Intent.GENERAL_QA
        return await self._llm_classify(msg)
