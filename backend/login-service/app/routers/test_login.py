import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services import jwt_service

logger = logging.getLogger("app.test_login")

router = APIRouter(prefix="/test")


class TestLoginRequest(BaseModel):
    user_id: int


@router.post("/login")
async def test_login(payload: TestLoginRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """부하테스트 전용 — 소셜 로그인 콜백과 동일한 내부 처리(사용자 조회 +
    JWT 발급)만 태우고 외부 IdP 왕복은 건너뛴다. app/main.py에서
    settings.enable_test_login이 True일 때만 라우터가 등록된다."""
    user = await db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    token = jwt_service.create_access_token(user.id, "test", user.display_name or "부하테스트")
    logger.info("test login issued: user_id=%s", user.id)
    return {"status": "SUCCESS", "token": token}
