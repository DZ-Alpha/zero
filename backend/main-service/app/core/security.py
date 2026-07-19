import logging
import time

import jwt
from fastapi import HTTPException, Response, status
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger("main_auth")

_UNAUTHORIZED = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰입니다.")


class UserIdentity(BaseModel):
    user_id: int
    nickname: str


def get_current_user_from_token(token: str, response: Response) -> UserIdentity:
    try:
        # algorithms=["HS256"] is an explicit allowlist — PyJWT will not honor
        # an "alg": "none" or other algorithm smuggled into the token header.
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        logger.warning("user auth denied: reason=invalid_or_expired_token")
        raise _UNAUTHORIZED from None

    user_id = int(payload["sub"])
    nickname = str(payload.get("nickname", ""))
    logger.info("user auth success: user_id=%s", user_id)

    # 슬라이딩 세션 — 같은 시크릿으로 클레임은 유지한 채 만료시각만 연장해
    # 재서명, 응답 헤더로 내려준다. 프론트는 이 헤더가 있으면 토큰을 교체한다.
    now = int(time.time())
    refreshed_payload = {**payload, "iat": now, "exp": now + settings.jwt_expire_minutes * 60}
    response.headers["X-Refreshed-Token"] = jwt.encode(refreshed_payload, settings.jwt_secret, algorithm="HS256")

    return UserIdentity(user_id=user_id, nickname=nickname)


def resolve_token(usr: str | None, authorization: str | None) -> str:
    """PRODUCTION_HANDOFF.md P0-4 — usr 쿼리파라미터/바디와 Authorization: Bearer
    헤더를 둘 다 받는다(헤더 우선). 기존 usr 방식 호출은 그대로 동작한다."""
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    if usr:
        return usr
    raise _UNAUTHORIZED
