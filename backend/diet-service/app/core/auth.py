import logging
import time

import jwt
from fastapi import Header, HTTPException, Query, Response

from app.core.config import settings

logger = logging.getLogger("diet_service.auth")

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


def get_current_user(response: Response, usr: str = Query(..., description="JWT 토큰")) -> dict:
    return _decode_and_refresh(usr, response)


def get_current_user_bearer(response: Response, authorization: str = Header(...)) -> dict:
    """식단 기록 CRUD(RC-0113~0117) 전용 — 신규 기능명세서가 `Authorization: Bearer`
    헤더를 명시해서, 기존 `usr` 쿼리파라미터 방식(get_current_user)과 별도로 둔다."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization 헤더 형식이 올바르지 않습니다.")
    token = authorization.removeprefix("Bearer ").strip()
    return _decode_and_refresh(token, response)
