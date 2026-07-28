from app.core.config import settings
from app.schemas import UserContext


def test_diet_service_url_has_default():
    assert settings.diet_service_url  # non-empty default


def test_user_context_today_fields_default_none():
    ctx = UserContext(user_id=0, logged_in=False, interests=[], has_allergy=False,
                      consent=False, daily_sugar_target_g=None, daily_calorie_target=None)
    assert ctx.today_sugar is None
    assert ctx.today_cal is None


def test_user_context_today_fields_accepted():
    ctx = UserContext(user_id=1, logged_in=True, interests=[], has_allergy=False,
                      consent=True, daily_sugar_target_g=50.0, daily_calorie_target=2000.0,
                      today_sugar=25.0, today_cal=750.0)
    assert ctx.today_sugar == 25.0
    assert ctx.today_cal == 750.0
