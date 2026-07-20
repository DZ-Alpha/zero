from app.handlers.base import FeatureHandler, HandlerInput, HandlerResult
from app.schemas import Intent


class Dispatcher:
    def __init__(self, handlers: dict[Intent, FeatureHandler]) -> None:
        self._handlers = handlers

    async def dispatch(self, intent: Intent, data: HandlerInput) -> HandlerResult:
        handler = self._handlers.get(intent)
        if handler is None:
            return HandlerResult(msg="아직 준비 중인 기능이에요. 곧 제공할게요.")
        return await handler.handle(data)
