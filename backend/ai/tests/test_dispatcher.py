from app.handlers.base import FeatureHandler, HandlerInput, HandlerResult
from app.router.dispatcher import Dispatcher
from app.schemas import Intent, UserContext


class _Echo(FeatureHandler):
    def __init__(self, label: str) -> None:
        self.label = label

    async def handle(self, data: HandlerInput) -> HandlerResult:
        return HandlerResult(msg=self.label)


def _input():
    ctx = UserContext(user_id=1, logged_in=False, interests=[], has_allergy=False,
                      consent=False, daily_sugar_target_g=None, daily_calorie_target=None)
    return HandlerInput(msg="x", img=None, template=None, context=ctx)


async def test_dispatch_routes_to_mapped_handler():
    disp = Dispatcher({Intent.GENERAL_QA: _Echo("general"), Intent.RECOMMEND: _Echo("recommend")})
    result = await disp.dispatch(Intent.RECOMMEND, _input())
    assert result.msg == "recommend"


async def test_dispatch_unmapped_intent_is_safe():
    disp = Dispatcher({Intent.GENERAL_QA: _Echo("general")})
    result = await disp.dispatch(Intent.ADMIN_ANALYTICS, _input())
    assert "준비" in result.msg
