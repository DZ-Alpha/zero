import logging
import time

import jwt
from fastapi import HTTPException, Response, status
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger("ai_auth")

_UNAUTHORIZED = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰입니다.")


class UserIdentity(BaseModel):
    user_id: int
    nickname: str


def get_current_user_from_token(token: str, response: Response) -> UserIdentity:
    try:
        # algorithms=["HS256"]은 명시적 allowlist — alg=none 등을 거부한다.
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        logger.warning("user auth denied: reason=invalid_or_expired_token")
        raise _UNAUTHORIZED from None

    user_id = int(payload["sub"])
    nickname = str(payload.get("nickname", ""))
    logger.info("user auth success: user_id=%s", user_id)

    now = int(time.time())
    refreshed = {**payload, "iat": now, "exp": now + settings.jwt_expire_minutes * 60}
    response.headers["X-Refreshed-Token"] = jwt.encode(refreshed, settings.jwt_secret, algorithm="HS256")

    return UserIdentity(user_id=user_id, nickname=nickname)
