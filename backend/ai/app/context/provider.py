from abc import ABC, abstractmethod

from app.schemas import UserContext


class UserContextProvider(ABC):
    """JWT 토큰으로 사용자 맥락을 로드한다. 더미/백엔드 구현으로 교체 가능."""

    @abstractmethod
    async def load(self, token: str) -> UserContext:
        ...


def build_provider(source: str) -> "UserContextProvider":
    from app.core.config import settings
    if source == "backend":
        from app.context.backend import BackendUserContextProvider
        return BackendUserContextProvider(login_url=settings.login_service_url,
                                          main_url=settings.main_service_url)
    from app.context.dummy import DummyUserContextProvider
    return DummyUserContextProvider()
