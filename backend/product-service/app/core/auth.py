import logging

import jwt
from fastapi import HTTPException, Query

from app.core.config import settings

logger = logging.getLogger("product_service.auth")

_ALLOWED_ALGORITHMS = ["HS256"]


def get_current_user(usr: str = Query(...)) -> dict:
    try:
        payload = jwt.decode(
            usr,
            settings.jwt_secret,
            algorithms=_ALLOWED_ALGORITHMS,
        )
    except jwt.ExpiredSignatureError:
        logger.warning("auth: expired token")
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다.")
    except jwt.InvalidTokenError:
        logger.warning("auth: invalid token")
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    return payload


def get_current_admin(usr: str = Query(...)) -> dict:
    payload = get_current_user(usr)
    if payload.get("role") != "admin":
        logger.warning("auth: non-admin access attempt user_id=%r", payload.get("user_id"))
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return payload
