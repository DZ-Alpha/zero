import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("app.turnstile")

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: str) -> bool:
    # Cloudflare can answer with a non-200 (e.g. malformed/misconfigured secret)
    # instead of the usual 200 + {"success": false} — treat any failure to reach
    # a clean verdict as "not verified" rather than crashing the login request.
    try:
        # 명시적 타임아웃 — oauth/__init__.py의 OAUTH_HTTP_TIMEOUT과 같은 이유다
        # (httpx 기본값 5초에 암묵적으로 기대고 있었음). 여긴 로그인 앞단이고
        # 실패해도 아래에서 "미검증"으로 떨어지므로 read도 3초로 줄인다.
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=3.0)) as client:
            response = await client.post(
                VERIFY_URL,
                data={"secret": settings.turnstile_secret_key, "response": token},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as error:
        logger.warning("turnstile verification failed: reason=request_error error=%r", str(error))
        return False

    if not payload.get("success"):
        logger.info("turnstile verification failed: reason=rejected error_codes=%r", payload.get("error-codes"))

    return bool(payload.get("success"))
