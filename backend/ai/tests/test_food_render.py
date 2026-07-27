from app.handlers.food_render import render_food_analysis
from app.schemas import UserContext


def _ctx(target=None):
    return UserContext(user_id=0, logged_in=bool(target), interests=[], has_allergy=False,
                       consent=True, daily_sugar_target_g=target, daily_calorie_target=None)


def test_empty_result_asks_retry():
    out = render_food_analysis({"list-diet": [], "confidence": 0.9,
                                "needs_user_confirmation": True}, _ctx())
    assert "찾지 못" in out


def test_single_food_confident():
    result = {"list-diet": [{"name": "초코케이크", "dang": 45, "calo": 380}],
              "confidence": 0.9, "needs_user_confirmation": False}
    out = render_food_analysis(result, _ctx())
    assert "초코케이크" in out
    assert "45" in out and "380" in out


def test_low_confidence_hedges():
    result = {"list-diet": [{"name": "초코케이크", "dang": 45, "calo": 380}],
              "confidence": 0.4, "needs_user_confirmation": True}
    out = render_food_analysis(result, _ctx())
    assert "확실하진" in out or "확인해" in out


def test_multiple_foods_sum():
    result = {"list-diet": [{"name": "케이크", "dang": 40, "calo": 300},
                            {"name": "아메리카노", "dang": 5, "calo": 10}],
              "confidence": 0.9, "needs_user_confirmation": False}
    out = render_food_analysis(result, _ctx())
    assert "케이크" in out and "아메리카노" in out
    assert "45" in out


def test_personalization_when_target_present():
    result = {"list-diet": [{"name": "케이크", "dang": 45, "calo": 300}],
              "confidence": 0.9, "needs_user_confirmation": False}
    out = render_food_analysis(result, _ctx(target=48))
    assert "48" in out


def test_no_personalization_without_target():
    result = {"list-diet": [{"name": "케이크", "dang": 45, "calo": 300}],
              "confidence": 0.9, "needs_user_confirmation": False}
    out = render_food_analysis(result, _ctx(target=None))
    assert "목표" not in out
