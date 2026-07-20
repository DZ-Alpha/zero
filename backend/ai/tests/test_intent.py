from app.router.intent import IntentClassifier
from app.schemas import Intent


async def _fake_llm(msg: str) -> Intent:
    # 테스트용 결정적 분류기 — 실제 Bedrock 대체.
    if "추천" in msg:
        return Intent.RECOMMEND
    return Intent.GENERAL_QA


def _classifier():
    return IntentClassifier(llm_classify=_fake_llm)


async def test_image_forces_product_analysis():
    intent = await _classifier().classify(msg="이거 뭐야?", has_image=True)
    assert intent is Intent.PRODUCT_ANALYSIS


async def test_image_forces_product_even_without_msg():
    intent = await _classifier().classify(msg=None, has_image=True)
    assert intent is Intent.PRODUCT_ANALYSIS


async def test_text_delegates_to_llm():
    intent = await _classifier().classify(msg="저당 상품 추천해줘", has_image=False)
    assert intent is Intent.RECOMMEND


async def test_general_question_delegates_to_llm():
    intent = await _classifier().classify(msg="탄수화물이 뭐야?", has_image=False)
    assert intent is Intent.GENERAL_QA
