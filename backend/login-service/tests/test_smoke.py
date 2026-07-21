# 2026-07-21, pytest opt-in 게이트 첫 적용 (build-test.yml의 Pytest 스텝 참고).
# import 수준(smoke check)을 넘어 "앱이 조립되고 핵심 라우트가 등록되는가"까지 검증한다.
# TestClient는 일부러 쓰지 않는다 - lifespan(DB/Redis 연결)이 CI에서 돌면 외부 의존이 생긴다.
from app.main import app


def test_app_constructed():
    assert app.title == "Final Team Alpha API"


def test_health_route_registered():
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/health" in paths
