import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services import user_store

logger = logging.getLogger("app.webhooks")

router = APIRouter(prefix="/webhooks")


@router.post("/naver/unlink")
async def naver_unlink(
    clientId: str,  # noqa: N803 (Naver's own query param casing)
    encryptUniqueId: str,  # noqa: N803
    timestamp: str,
    signature: str,
) -> dict[str, str]:
    """Naver's '연결 끊기 콜백'. Live traffic (observed 2026-07-14) is POST with
    clientId/encryptUniqueId/timestamp/signature query params — NOT the simple
    GET client_id/user shape documented on the console screen. encryptUniqueId
    is an encrypted value, not the raw provider_user_id, so we can't match it
    against social_accounts.provider_user_id yet without the decryption/signature
    spec. For now: verify nothing (unknown scheme), just log the raw payload so
    we can implement decryption once we have Naver's exact algorithm docs.
    """
    logger.info(
        "naver unlink webhook raw: clientId=%s encryptUniqueId=%s timestamp=%s signature=%s",
        clientId,
        encryptUniqueId,
        timestamp,
        signature,
    )
    if clientId != settings.naver_client_id:
        logger.warning("naver unlink webhook: unexpected clientId=%s", clientId)

    logger.warning("naver unlink webhook: encryptUniqueId decryption not yet implemented, no action taken")

    return {"result": "success"}


@router.post("/kakao/unlink")
async def kakao_unlink(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Kakao's '연결 해제 웹훅'. Payload format observed empirically since Kakao's
    docs are thin on exact field names — accept both form and JSON bodies and look
    for the provider user id under any of the field names Kakao is known to use.
    """
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body: dict[str, object] = await request.json()
    else:
        form = await request.form()
        body = dict(form)

    logger.info("kakao unlink webhook raw body: %s", body)

    user_id = body.get("user_id") or body.get("id")
    if user_id is None:
        logger.warning("kakao unlink webhook: could not find user id in payload=%s", body)
        return {"result": "success"}

    action = await user_store.handle_provider_unlink(db, provider="kakao", provider_user_id=str(user_id))
    logger.info("kakao unlink webhook: user=%s action=%s", user_id, action)

    return {"result": "success"}
