import uuid

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag
from app.models.user_preference import UserPreference

_TAG_BASED_TYPES = {"INTEREST_CATEGORY", "ALLERGEN"}
_ALLOWED_TAG_TYPES = {
    "INTEREST_CATEGORY": {"HEALTH_LABEL", "CATEGORY"},
    "ALLERGEN": {"ALLERGEN"},
}


class InvalidPreferenceError(Exception):
    pass


class TagNotFoundError(Exception):
    pass


class DuplicatePreferenceError(Exception):
    pass


def _validate_tag_type(preference_type: str, tag: Tag) -> None:
    allowed = _ALLOWED_TAG_TYPES.get(preference_type)
    if allowed is None or tag.tag_type not in allowed:
        allowed_text = ", ".join(sorted(allowed or []))
        raise InvalidPreferenceError(
            f"{preference_type}에는 {allowed_text} 태그만 저장할 수 있습니다."
        )


def _normalize_custom_values(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = " ".join(raw_value.split()).strip()
        key = value.casefold()
        if not value or key in seen:
            continue
        if len(value) > 255:
            raise InvalidPreferenceError("주의 성분은 255자 이하로 입력해 주세요.")
        seen.add(key)
        normalized.append(value)
    return normalized


async def list_preferences(db: AsyncSession, user_id: int) -> list[UserPreference]:
    stmt = select(UserPreference).where(UserPreference.user_id == user_id)
    return list((await db.execute(stmt)).scalars().all())


async def list_preferences_with_tags(
    db: AsyncSession, user_id: int
) -> list[tuple[UserPreference, Tag | None]]:
    stmt = (
        select(UserPreference, Tag)
        .outerjoin(Tag, Tag.tag_id == UserPreference.tag_id)
        .where(UserPreference.user_id == user_id)
        .order_by(UserPreference.preference_type, UserPreference.created_at)
    )
    return [(preference, tag) for preference, tag in (await db.execute(stmt)).all()]


async def add_preference(
    db: AsyncSession,
    user_id: int,
    preference_type: str,
    tag_id: uuid.UUID | None,
    custom_value: str | None,
) -> UserPreference:
    if preference_type in _TAG_BASED_TYPES:
        if tag_id is None or custom_value is not None:
            raise InvalidPreferenceError(f"{preference_type}에는 tagId만 지정해야 합니다.")
        tag = await db.get(Tag, tag_id)
        if tag is None or not tag.active:
            raise TagNotFoundError("존재하지 않거나 비활성화된 태그입니다.")
        _validate_tag_type(preference_type, tag)
    elif preference_type == "CAUTION_INGREDIENT":
        if custom_value is None or tag_id is not None:
            raise InvalidPreferenceError("CAUTION_INGREDIENT에는 customValue만 지정해야 합니다.")
        custom_values = _normalize_custom_values([custom_value])
        if not custom_values:
            raise InvalidPreferenceError("주의 성분을 입력해 주세요.")
        custom_value = custom_values[0]
    else:
        raise InvalidPreferenceError(f"지원하지 않는 preferenceType입니다: {preference_type!r}")

    preference = UserPreference(
        preference_id=uuid.uuid4(),
        user_id=user_id,
        preference_type=preference_type,
        tag_id=tag_id,
        custom_value=custom_value,
    )
    db.add(preference)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise DuplicatePreferenceError("이미 등록된 선호 정보입니다.") from error

    await db.refresh(preference)
    return preference


async def replace_preferences(
    db: AsyncSession,
    user_id: int,
    interest_tag_ids: list[uuid.UUID],
    allergen_tag_ids: list[uuid.UUID],
    caution_ingredients: list[str],
) -> list[tuple[UserPreference, Tag | None]]:
    interest_ids = list(dict.fromkeys(interest_tag_ids))
    allergen_ids = list(dict.fromkeys(allergen_tag_ids))
    all_tag_ids = list(dict.fromkeys([*interest_ids, *allergen_ids]))

    tags_by_id: dict[uuid.UUID, Tag] = {}
    if all_tag_ids:
        tag_stmt = select(Tag).where(Tag.tag_id.in_(all_tag_ids), Tag.active.is_(True))
        tags_by_id = {tag.tag_id: tag for tag in (await db.execute(tag_stmt)).scalars().all()}
        missing = [tag_id for tag_id in all_tag_ids if tag_id not in tags_by_id]
        if missing:
            raise TagNotFoundError("존재하지 않거나 비활성화된 태그가 포함되어 있습니다.")

    for tag_id in interest_ids:
        _validate_tag_type("INTEREST_CATEGORY", tags_by_id[tag_id])
    for tag_id in allergen_ids:
        _validate_tag_type("ALLERGEN", tags_by_id[tag_id])

    caution_values = _normalize_custom_values(caution_ingredients)

    await db.execute(delete(UserPreference).where(UserPreference.user_id == user_id))
    for preference_type, tag_ids in (
        ("INTEREST_CATEGORY", interest_ids),
        ("ALLERGEN", allergen_ids),
    ):
        for tag_id in tag_ids:
            db.add(
                UserPreference(
                    preference_id=uuid.uuid4(),
                    user_id=user_id,
                    preference_type=preference_type,
                    tag_id=tag_id,
                    custom_value=None,
                )
            )
    for custom_value in caution_values:
        db.add(
            UserPreference(
                preference_id=uuid.uuid4(),
                user_id=user_id,
                preference_type="CAUTION_INGREDIENT",
                tag_id=None,
                custom_value=custom_value,
            )
        )

    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise InvalidPreferenceError("선호 정보를 저장하지 못했습니다.") from error

    return await list_preferences_with_tags(db, user_id)


async def remove_preference(db: AsyncSession, user_id: int, preference_id: uuid.UUID) -> bool:
    preference = await db.get(UserPreference, preference_id)
    if preference is None or preference.user_id != user_id:
        return False
    await db.delete(preference)
    await db.commit()
    return True
