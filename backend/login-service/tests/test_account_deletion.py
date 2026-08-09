from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.user_store import AccountDeletionBlockedError, delete_user


@pytest.mark.asyncio
async def test_delete_user_is_blocked_when_user_owns_a_room() -> None:
    db = MagicMock()
    db.get = AsyncMock(return_value=SimpleNamespace(id=7))
    blocker_result = MagicMock()
    blocker_result.one.return_value = SimpleNamespace(owned_rooms=1, authored_notices=0)
    db.execute = AsyncMock(return_value=blocker_result)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    with pytest.raises(AccountDeletionBlockedError) as error:
        await delete_user(db, user_id=7)

    assert error.value.owned_rooms == 1
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_user_removes_invites_before_account() -> None:
    user = SimpleNamespace(id=7)
    db = MagicMock()
    db.get = AsyncMock(return_value=user)
    blocker_result = MagicMock()
    blocker_result.one.return_value = SimpleNamespace(owned_rooms=0, authored_notices=0)
    db.execute = AsyncMock(side_effect=[blocker_result, MagicMock(), MagicMock()])
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    await delete_user(db, user_id=7)

    assert db.execute.await_count == 3
    db.delete.assert_awaited_once_with(user)
    db.commit.assert_awaited_once()
