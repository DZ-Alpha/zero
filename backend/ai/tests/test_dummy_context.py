import pytest

from app.context.dummy import DummyUserContextProvider


@pytest.fixture
def provider():
    return DummyUserContextProvider()


async def test_full_scenario_has_targets(provider):
    ctx = await provider.load("full")
    assert ctx.logged_in is True
    assert ctx.consent is True
    assert ctx.daily_sugar_target_g == 48.0
    assert ctx.daily_calorie_target == 1900.0
    assert "저당" in ctx.interests


async def test_calc_scenario_consent_but_no_targets(provider):
    ctx = await provider.load("calc")
    assert ctx.consent is True
    assert ctx.daily_sugar_target_g is None


async def test_limited_scenario_no_consent(provider):
    ctx = await provider.load("limited")
    assert ctx.logged_in is True
    assert ctx.consent is False
    assert ctx.daily_sugar_target_g is None


async def test_anonymous_scenario_not_logged_in(provider):
    ctx = await provider.load("")
    assert ctx.logged_in is False
    assert ctx.interests == []
