from app.context.provider import UserContextProvider
from app.schemas import UserContext

# 설계 §6 4종 시나리오. 개인화·폴백·환각방지 검증용.
_SCENARIOS = {
    "full": UserContext(user_id=1, logged_in=True, interests=["저당", "고단백"], has_allergy=True,
                        consent=True, daily_sugar_target_g=48.0, daily_calorie_target=1900.0),
    "calc": UserContext(user_id=2, logged_in=True, interests=["저당"], has_allergy=False,
                        consent=True, daily_sugar_target_g=None, daily_calorie_target=None),
    "limited": UserContext(user_id=3, logged_in=True, interests=["저당"], has_allergy=False,
                           consent=False, daily_sugar_target_g=None, daily_calorie_target=None),
}

_ANONYMOUS = UserContext(user_id=0, logged_in=False, interests=[], has_allergy=False,
                         consent=False, daily_sugar_target_g=None, daily_calorie_target=None)


class DummyUserContextProvider(UserContextProvider):
    async def load(self, token: str) -> UserContext:
        return _SCENARIOS.get(token, _ANONYMOUS)
