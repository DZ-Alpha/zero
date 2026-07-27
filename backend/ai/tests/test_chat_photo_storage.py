import pytest

from app.services import chat_photo_storage as cps


async def test_store_returns_none_when_not_configured(monkeypatch):
    monkeypatch.setattr(cps, "_configured", lambda: False)
    result = await cps.store_best_effort(1, "image/png", b"x")
    assert result is None


async def test_store_returns_none_for_unsupported_media(monkeypatch):
    monkeypatch.setattr(cps, "_configured", lambda: True)
    result = await cps.store_best_effort(1, "image/heic", b"x")
    assert result is None


async def test_store_returns_object_key_on_success(monkeypatch):
    monkeypatch.setattr(cps, "_configured", lambda: True)
    monkeypatch.setattr(cps, "_store_sync", lambda k, m, b: None)
    result = await cps.store_best_effort(7, "image/png", b"x")
    assert result is not None
    assert result.startswith("7/")
    assert result.endswith(".png")


async def test_store_returns_none_on_storage_error(monkeypatch):
    from botocore.exceptions import BotoCoreError
    monkeypatch.setattr(cps, "_configured", lambda: True)
    def boom(k, m, b):
        raise BotoCoreError()
    monkeypatch.setattr(cps, "_store_sync", boom)
    result = await cps.store_best_effort(7, "image/png", b"x")
    assert result is None


def test_presign_returns_relative_b_path(monkeypatch):
    class _FakeClient:
        def generate_presigned_url(self, *a, **k):
            return "http://minio-internal:9000/chat-photos/7/x.png?X-Amz-Signature=abc&X-Amz-Date=1"
    monkeypatch.setattr(cps, "_configured", lambda: True)
    monkeypatch.setattr(cps, "_client", lambda: _FakeClient())
    url = cps.presign_chat_photo_url("7/x.png")
    assert url.startswith("/b/chat-photos/7/x.png?")
    assert "X-Amz-Signature=abc" in url


def test_presign_returns_none_when_not_configured(monkeypatch):
    monkeypatch.setattr(cps, "_configured", lambda: False)
    assert cps.presign_chat_photo_url("7/x.png") is None
