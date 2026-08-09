import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_from_token, resolve_token
from app.models.tag import Tag
from app.models.user_preference import UserPreference
from app.services.preference_store import (
    DuplicatePreferenceError,
    InvalidPreferenceError,
    TagNotFoundError,
    add_preference,
    list_preferences_with_tags,
    remove_preference,
    replace_preferences,
)

router = APIRouter(prefix="/home/preferences")


class AddPreferenceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    usr: str | None = None
    preference_type: Annotated[str, Field(alias="preferenceType")]
    tag_id: Annotated[uuid.UUID | None, Field(alias="tagId")] = None
    custom_value: Annotated[str | None, Field(alias="customValue")] = None


class ReplacePreferencesRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    usr: str | None = None
    interest_tag_ids: list[uuid.UUID] = Field(default_factory=list, alias="interestTagIds")
    allergen_tag_ids: list[uuid.UUID] = Field(default_factory=list, alias="allergenTagIds")
    caution_ingredients: list[str] = Field(default_factory=list, alias="cautionIngredients")


def _preference_payload(preference: UserPreference, tag: Tag | None) -> dict[str, object]:
    return {
        "preferenceId": str(preference.preference_id),
        "preferenceType": preference.preference_type,
        "tagId": str(preference.tag_id) if preference.tag_id else None,
        "tagType": tag.tag_type if tag else None,
        "tagCode": tag.tag_code if tag else None,
        "tagName": tag.tag_name if tag else None,
        "description": tag.description if tag else None,
        "cautionText": tag.caution_text if tag else None,
        "sourceUrl": tag.source_url if tag else None,
        "customValue": preference.custom_value,
    }


@router.get("")
async def get_preferences(
    response: Response,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = get_current_user_from_token(resolve_token(None, authorization), response)
    preferences = await list_preferences_with_tags(db, user.user_id)
    return {"preferences": [_preference_payload(p, tag) for p, tag in preferences]}


@router.put("")
async def put_preferences(
    payload: ReplacePreferencesRequest,
    response: Response,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = get_current_user_from_token(resolve_token(payload.usr, authorization), response)
    try:
        preferences = await replace_preferences(
            db,
            user.user_id,
            payload.interest_tag_ids,
            payload.allergen_tag_ids,
            payload.caution_ingredients,
        )
    except InvalidPreferenceError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except TagNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {
        "status": "SUCCESS",
        "preferences": [_preference_payload(p, tag) for p, tag in preferences],
    }


@router.post("")
async def create_preference(
    payload: AddPreferenceRequest,
    response: Response,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = get_current_user_from_token(resolve_token(payload.usr, authorization), response)
    try:
        preference = await add_preference(
            db, user.user_id, payload.preference_type, payload.tag_id, payload.custom_value
        )
    except InvalidPreferenceError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except TagNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except DuplicatePreferenceError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return {"status": "SUCCESS", "preferenceId": str(preference.preference_id)}


@router.delete("/{preference_id}")
async def delete_preference(
    preference_id: uuid.UUID,
    response: Response,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    user = get_current_user_from_token(resolve_token(None, authorization), response)
    deleted = await remove_preference(db, user.user_id, preference_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="선호 정보를 찾을 수 없습니다.")
    return {"status": "SUCCESS"}
