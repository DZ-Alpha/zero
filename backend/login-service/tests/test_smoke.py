# 2026-07-21, pytest opt-in 게이트 첫 적용 (build-test.yml의 Pytest 스텝 참고).
# import 수준(smoke check)을 넘어 "앱이 조립되고 health 라우트가 정의되는가"까지 검증한다.
#
# 검증 대상을 app.routes가 아니라 라우터 객체로 잡은 이유(2026-07-21 CI 실측):
#  - 현재 fastapi(0.139)는 include_router 등록을 앱 시작 시점까지 지연시켜,
#    startup 전 app.routes에는 기본 문서 라우트만 보인다(진단 run 88553097068).
#  - TestClient로 실요청을 보내는 방법은 lifespan의 create_all이 예외 처리 없이
#    PostgreSQL에 연결해서 CI에 외부 의존이 생기므로 배제.
#  - APIRouter의 라우트는 데코레이터 시점에 즉시 등록되므로 버전 비의존적이다.
from app.main import app
from app.routers.health import router as health_router


def test_app_constructed():
    assert app.title == "Final Team Alpha API"


def test_health_route_defined():
    paths = {getattr(route, "path", None) for route in health_router.routes}
    assert "/health" in paths, f"router routes={sorted(str(p) for p in paths)}"
