from app.context.backend import BackendUserContextProvider
from app.context.provider import build_provider


def test_build_backend_provider_has_diet_url():
    p = build_provider("backend")
    assert isinstance(p, BackendUserContextProvider)
    assert p._diet_url  # non-empty (settings.diet_service_url)


def test_build_dummy_provider_still_works():
    from app.context.dummy import DummyUserContextProvider
    assert isinstance(build_provider("dummy"), DummyUserContextProvider)
