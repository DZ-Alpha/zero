from fastapi import APIRouter, Header, Response

from app.core.security import get_current_user_from_token, resolve_token

router = APIRouter(prefix="/home")


@router.get("/me")
async def get_current_user_identity(
    response: Response, usr: str | None = None, authorization: str | None = Header(None)
) -> dict[str, object]:
    user = get_current_user_from_token(resolve_token(usr, authorization), response)
    return {"userId": user.user_id, "nickname": user.nickname}
