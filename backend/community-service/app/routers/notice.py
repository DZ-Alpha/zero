import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin_from_token, get_current_user_from_token, resolve_token
from app.models.notice import Notice
from app.services.notice_store import (
    NoticeNotFoundError,
    count_likes,
    create_notice,
    delete_notice,
    get_notice,
    list_notices,
    toggle_like,
    update_notice,
)

router = APIRouter(prefix="/community/notice")


class NoticeCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    usr: str | None = None
    name: str
    desc: str
    tag: str | None = None
    thumbnail: str | None = None
    external_url: Annotated[str | None, Field(alias="externalUrl")] = None


class NoticeUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    usr: str | None = None
    name: str | None = None
    desc: str | None = None
    tag: str | None = None
    thumbnail: str | None = None
    external_url: Annotated[str | None, Field(alias="externalUrl")] = None


def _list_item(notice: Notice) -> dict[str, object]:
    return {
        "id": str(notice.notice_id),
        "article": {
            "name": notice.title,
            "desc": notice.content[:100],
            "thumbnail": notice.thumbnail_url,
        },
    }


@router.get("")
async def get_notice_list(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    notices = await list_notices(db)
    return {"list": [_list_item(notice) for notice in notices]}


@router.get("/{notice_id}")
async def get_notice_detail(notice_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    try:
        notice = await get_notice(db, notice_id)
    except NoticeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    like_count = await count_likes(db, notice_id)
    return {
        "name": notice.title,
        "desc": notice.content,
        "tag": notice.hashtag,
        "thumbnail": notice.thumbnail_url,
        "externalUrl": notice.external_url,
        "recommend": like_count,
    }


@router.post("")
async def write_notice(
    payload: NoticeCreateRequest,
    response: Response,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    admin = get_current_admin_from_token(resolve_token(payload.usr, authorization), response)
    notice = await create_notice(
        db,
        admin.user_id,
        title=payload.name,
        content=payload.desc,
        external_url=payload.external_url,
        thumbnail_url=payload.thumbnail,
        hashtag=payload.tag,
    )
    return {"status": "SUCCESS", "id": str(notice.notice_id)}


@router.put("/{notice_id}")
async def edit_notice(
    notice_id: uuid.UUID,
    payload: NoticeUpdateRequest,
    response: Response,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    get_current_admin_from_token(resolve_token(payload.usr, authorization), response)
    try:
        notice = await update_notice(
            db,
            notice_id,
            title=payload.name,
            content=payload.desc,
            external_url=payload.external_url,
            thumbnail_url=payload.thumbnail,
            hashtag=payload.tag,
        )
    except NoticeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return {
        "status": "SUCCESS",
        "name": notice.title,
        "desc": notice.content,
        "tag": notice.hashtag,
        "thumbnail": notice.thumbnail_url,
    }


@router.delete("/{notice_id}")
async def remove_notice(
    notice_id: uuid.UUID,
    response: Response,
    usr: str | None = None,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    get_current_admin_from_token(resolve_token(usr, authorization), response)
    try:
        await delete_notice(db, notice_id)
    except NoticeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return {"status": "SUCCESS"}


@router.post("/{notice_id}/like")
async def like_notice(
    notice_id: uuid.UUID,
    response: Response,
    usr: str | None = None,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = get_current_user_from_token(resolve_token(usr, authorization), response)
    try:
        liked, count = await toggle_like(db, notice_id, user.user_id)
    except NoticeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return {"status": "SUCCESS", "liked": liked, "recommend": count}
