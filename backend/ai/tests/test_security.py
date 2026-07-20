import time

import jwt
import pytest
from fastapi import HTTPException, Response

from app.core.config import settings
from app.core.security import UserIdentity, get_current_user_from_token


def make_token(user_id: int = 7, nickname: str = "지은", exp_offset: int = 3600) -> str:
    now = int(time.time())
    payload = {"sub": str(user_id), "nickname": nickname, "iat": now, "exp": now + exp_offset}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def test_valid_token_returns_identity():
    response = Response()
    identity = get_current_user_from_token(make_token(), response)
    assert isinstance(identity, UserIdentity)
    assert identity.user_id == 7
    assert identity.nickname == "지은"


def test_valid_token_sets_refreshed_header():
    response = Response()
    get_current_user_from_token(make_token(), response)
    assert response.headers.get("X-Refreshed-Token")


def test_invalid_token_raises_401():
    with pytest.raises(HTTPException) as exc:
        get_current_user_from_token("garbage.token.value", Response())
    assert exc.value.status_code == 401


def test_alg_none_token_rejected():
    # alg=none 스머글링 방지 — HS256 allowlist라 거부돼야 한다.
    payload = {"sub": "7", "nickname": "x", "exp": int(time.time()) + 3600}
    forged = jwt.encode(payload, key="", algorithm="none")
    with pytest.raises(HTTPException) as exc:
        get_current_user_from_token(forged, Response())
    assert exc.value.status_code == 401
