import time

import jwt

from app.core.config import settings


def create_access_token(user_id: int, provider: str, nickname: str) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "provider": provider,
        "nickname": nickname,
        "iat": now,
        "exp": now + settings.jwt_expire_minutes * 60,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_user_id(token: str) -> int:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    return int(payload["sub"])
