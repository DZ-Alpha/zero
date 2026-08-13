"""DB 접속/기동 설정의 기본값이 '지금 온프렘 동작'에서 벗어나지 않게 잡아둔다.

2026-08-13 감사 C-1/C-2로 startup DDL과 커넥션 풀을 환경변수로 뺐다. 뺀 목적은
RDS에서 코드 수정 없이 끌 수 있게 하는 것이지 지금 동작을 바꾸는 게 아니다.
기본값을 잘못 내리면:
  - db_auto_migrate=False → 컬럼이 없는 채로 떠서 첫 INSERT부터 죽는다
  - pool 축소 → 부하 시점 community-svc가 파드당 8개를 다 잡고 있던 관측(A-5)
    구조가 남아 있어 pool_timeout=10에 걸린다
값 조정은 RDS 컷오버 때 파드 수·트래픽과 함께 결정한다(db/migrations/README.md).
"""

import importlib

import pytest


@pytest.fixture
def fresh_settings(monkeypatch):
    """환경변수를 지운 상태에서 Settings를 새로 만든다(.env 영향 배제)."""
    def _load(**env: str):
        for key in ("DB_AUTO_MIGRATE", "DB_POOL_SIZE", "DB_MAX_OVERFLOW"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        config = importlib.import_module("app.core.config")
        return config.Settings(_env_file=None)
    return _load


def test_defaults_match_current_production(fresh_settings) -> None:
    settings = fresh_settings()
    assert settings.db_auto_migrate is True, "기본값이 False면 스키마 없는 환경에서 조용히 뜬다"
    assert settings.db_pool_size == 5
    assert settings.db_max_overflow == 3


def test_rds_profile_can_be_set_by_env(fresh_settings) -> None:
    """계획서 A-15의 RDS 값(2+1)이 코드 수정 없이 들어가는지."""
    settings = fresh_settings(DB_AUTO_MIGRATE="false", DB_POOL_SIZE="2", DB_MAX_OVERFLOW="1")
    assert settings.db_auto_migrate is False
    assert settings.db_pool_size == 2
    assert settings.db_max_overflow == 1
