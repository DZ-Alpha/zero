from sqlalchemy.ext.asyncio import AsyncSession

from app.models.room_idempotency_key import RoomIdempotencyKey


async def get_cached(db: AsyncSession, key: str, user_id: int) -> dict | None:
    row = await db.get(RoomIdempotencyKey, {"key": key, "user_id": user_id})
    return row.response_body if row is not None else None


async def store(db: AsyncSession, key: str, user_id: int, status: int, body: dict) -> None:
    db.add(RoomIdempotencyKey(key=key, user_id=user_id, response_status=status, response_body=body))
    await db.commit()
