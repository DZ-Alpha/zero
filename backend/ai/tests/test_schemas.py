import pytest
from pydantic import ValidationError

from app.schemas import ChatbotRequest, ChatbotResponse, Intent, UserContext


def test_request_accepts_msg_only():
    req = ChatbotRequest(usr="tok", msg="탄수화물이 뭐야?")
    assert req.msg == "탄수화물이 뭐야?"
    assert req.img is None


def test_request_requires_msg_or_img():
    with pytest.raises(ValidationError):
        ChatbotRequest(usr="tok")


def test_response_serializes_with_hyphen_aliases():
    resp = ChatbotResponse(cs_partner="당당봇", time="2026-07-20T00:00:00Z", msg="안녕하세요", is_img=False)
    dumped = resp.model_dump(by_alias=True)
    assert dumped["cs-partner"] == "당당봇"
    assert dumped["is-img"] is False


def test_user_context_optional_targets():
    ctx = UserContext(user_id=1, logged_in=True, interests=["저당"], has_allergy=False,
                      consent=False, daily_sugar_target_g=None, daily_calorie_target=None)
    assert ctx.daily_sugar_target_g is None


def test_intent_values():
    assert Intent.GENERAL_QA.value == "general_qa"
    assert Intent("product_analysis") is Intent.PRODUCT_ANALYSIS
