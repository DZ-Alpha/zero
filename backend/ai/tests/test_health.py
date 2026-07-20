async def test_health_returns_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_settings_defaults():
    from app.core.config import settings
    assert settings.user_context_source == "dummy"
    assert settings.jwt_expire_minutes == 180


def test_rag_settings_defaults():
    from app.core.config import settings
    assert settings.rag_enabled is False
    assert settings.embed_region  # 비어있지 않음
