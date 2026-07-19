import logging
import time

import jwt
from fastapi import Header, HTTPException, Query, Response

from app.core.config import settings

logger = logging.getLogger("ingredients_service.auth")

_ALLOWED_ALGORITHMS = {"HS256"}


def _decode_and_refresh(token: str, response: Response) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=list(_ALLOWED_ALGORITHMS),
        )
    except jwt.ExpiredSignatureError:
        # 토큰 값 자체는 절대 로그에 남기지 않는다 (민감정보 — ASVS V16.4.1).
        logger.warning("auth: expired token")
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다.")
    except jwt.InvalidTokenError:
        logger.warning("auth: invalid token")
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")

    # 슬라이딩 세션 — 같은 시크릿으로 클레임은 유지한 채 만료시각만 연장해
    # 재서명, 응답 헤더로 내려준다. 프론트는 이 헤더가 있으면 토큰을 교체한다.
    now = int(time.time())
    refreshed_payload = {**payload, "iat": now, "exp": now + settings.jwt_expire_minutes * 60}
    response.headers["X-Refreshed-Token"] = jwt.encode(
        refreshed_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )

    return payload


def get_current_user(
    response: Response,
    usr: str | None = Query(None, description="JWT 토큰 (또는 Authorization: Bearer 헤더)"),
    authorization: str | None = Header(None),
) -> dict:
    """PRODUCTION_HANDOFF.md P0-4 — usr 쿼리파라미터와 Authorization: Bearer 헤더를
    둘 다 받는다(헤더 우선). 기존 usr 방식 호출은 그대로 동작한다."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif usr:
        token = usr
    else:
        raise HTTPException(status_code=401, detail="인증 정보가 없습니다.")
    return _decode_and_refresh(token, response)


def get_current_admin(
    response: Response,
    usr: str | None = Query(None),
    authorization: str | None = Header(None),
) -> dict:
    payload = get_current_user(response, usr, authorization)
    if payload.get("role") != "admin":
        logger.warning("auth: non-admin access attempt user_id=%r", payload.get("user_id"))
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return payload
