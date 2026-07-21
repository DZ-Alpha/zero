"""CI 스모크 테스트 (pytest opt-in 게이트 첫 적용, 2026-07-21).

TestClient를 컨텍스트 매니저 없이 사용해 lifespan(외부 연결)을 실행하지 않고
라우팅과 응답만 검증한다 - 라우트 introspection 방식의 함정을 피한 행동형 테스트.
"""
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_200():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, World!"}
