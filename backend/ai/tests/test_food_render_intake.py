from app.handlers.food_render import render_food_analysis
from app.schemas import UserContext


def _ctx(**kw):
    base = dict(user_id=1, logged_in=True, interests=[], has_allergy=False, consent=True,
                daily_sugar_target_g=None, daily_calorie_target=None)
    base.update(kw)
    return UserContext(**base)


def _result(dang, calo, name="치즈떡볶이"):
    return {"list-diet": [{"name": name, "dang": dang, "calo": calo}],
            "confidence": 0.9, "needs_user_confirmation": False}


def test_cumulative_reaches_sugar_target():
    ctx = _ctx(daily_sugar_target_g=50, daily_calorie_target=2000,
               today_sugar=25, today_cal=750)
    out = render_food_analysis(_result(25, 950), ctx)
    # 가정법 + 오늘 누적 반영(25+25=50, 목표 50 도달)
    assert "드시면" in out or "먹으면" in out
    assert "50" in out          # 당류 합계 or 목표
    # 칼로리도 반영(750+950=1700)
    assert "1700" in out


def test_cumulative_under_target_shows_remaining():
    ctx = _ctx(daily_sugar_target_g=50, daily_calorie_target=2000,
               today_sugar=10, today_cal=300)
    out = render_food_analysis(_result(15, 400), ctx)
    # 10+15=25, 목표 50 → 남음
    assert "드시면" in out or "먹으면" in out
    assert "25" in out


def test_no_today_falls_back_to_target_only():
    ctx = _ctx(daily_sugar_target_g=50, today_sugar=None, today_cal=None)
    out = render_food_analysis(_result(25, 950), ctx)
    assert "목표" in out
    assert "드시면" not in out   # 누적 없으니 가정법 누적문장 아님


def test_no_target_shows_numbers_only():
    ctx = _ctx()  # 목표·누적 다 없음
    out = render_food_analysis(_result(25, 950), ctx)
    assert "치즈떡볶이" in out and "25" in out
    assert "목표" not in out


def test_gerund_never_claims_saved():
    # 저장된 것처럼 단정하지 않는다 — "저장" 표현 없음
    ctx = _ctx(daily_sugar_target_g=50, daily_calorie_target=2000, today_sugar=25, today_cal=750)
    out = render_food_analysis(_result(25, 950), ctx)
    assert "저장" not in out and "기록했" not in out
