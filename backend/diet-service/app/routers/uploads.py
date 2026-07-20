import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.auth import get_current_user
from app.services.storage import StorageNotConfiguredError, StorageUploadError, upload_diet_photo

logger = logging.getLogger("diet_service.uploads")

router = APIRouter(prefix="/uploads")

_MAX_BYTES = 10 * 1024 * 1024


@router.post("/diet-photo")
async def upload_diet_photo_endpoint(
    file: UploadFile = File(...),
    payload: dict = Depends(get_current_user),
) -> dict[str, str]:
    """gateway가 받은 식단 사진을 MinIO diet-photos 버킷에 저장하고
    object_key만 돌려준다 — 브라우저는 MinIO를 직접 보지 않는다."""
    user_id: int = payload["user_id"]

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="빈 파일입니다.")
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="사진 크기는 10MB 이하여야 합니다.")

    try:
        object_key = upload_diet_photo(user_id, file.content_type or "", data)
    except StorageNotConfiguredError as error:
        logger.error("diet photo upload not configured: %s", error)
        raise HTTPException(status_code=501, detail="사진 업로드 저장소가 아직 설정되지 않았습니다.") from error
    except StorageUploadError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return {"object_key": object_key}
