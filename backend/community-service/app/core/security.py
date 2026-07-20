import logging
import time

import jwt
from fastapi import HTTPException, Response, status
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger("community_auth")

_UNAUTHORIZED = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰입니다.")
_FORBIDDEN = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")


class UserIdentity(BaseModel):
    user_id: int
    role: str


def _refresh(payload: dict, response: Response) -> None:
    # 슬라이딩 세션 — 같은 시크릿으로 클레임은 유지한 채 만료시각만 연장해
    # 재서명, 응답 헤더로 내려준다. 프론트는 이 헤더가 있으면 토큰을 교체한다.
    now = int(time.time())
    refreshed_payload = {**payload, "iat": now, "exp": now + settings.jwt_expire_minutes * 60}
    response.headers["X-Refreshed-Token"] = jwt.encode(refreshed_payload, settings.jwt_secret, algorithm="HS256")


def get_current_user_from_token(token: str, response: Response) -> UserIdentity:
    try:
        # algorithms=["HS256"] is an explicit allowlist — PyJWT will not honor
        # an "alg": "none" or other algorithm smuggled into the token header.
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        logger.warning("auth denied: reason=invalid_or_expired_token")
        raise _UNAUTHORIZED from None

    user_id = int(payload["sub"])
    role = str(payload.get("role", "user"))
    logger.info("auth success: user_id=%s role=%s", user_id, role)
    _refresh(payload, response)
    return UserIdentity(user_id=user_id, role=role)


def resolve_token(usr: str | None, authorization: str | None) -> str:
    """PRODUCTION_HANDOFF.md P0-4 — usr 쿼리파라미터/바디와 Authorization: Bearer
    헤더를 둘 다 받는다(헤더 우선). 기존 usr 방식 호출은 그대로 동작한다."""
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    if usr:
        return usr
    raise _UNAUTHORIZED


def get_current_admin_from_token(token: str, response: Response) -> UserIdentity:
    """공지사항 쓰기/수정/삭제는 Admin Service를 통해서만 열어주는 게 자연스럽다
    (community-service.md, SC-0102 관리자 권한 분리와 일치) — 같은 role 클레임을
    admin-service와 동일하게 검사한다."""
    user = get_current_user_from_token(token, response)
    if user.role != "admin":
        logger.warning("authorization denied: reason=insufficient_role user_id=%s role=%s", user.user_id, user.role)
        raise _FORBIDDEN
    return user
