import hashlib
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.room import Room
from app.models.room_invite import RoomInvite
from app.models.room_meal_comment import RoomMealComment
from app.models.room_meal_reaction import RoomMealReaction
from app.models.room_meal_thread import RoomMealThread
from app.models.room_member import RoomMember
from app.models.room_nudge import RoomNudge
from app.models.room_report import RoomReport
from app.models.social_account_ref import SocialAccountRef
from app.models.user_ref import UserRef

MAX_ROOM_COUNT = 3
INVITE_CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
INVITE_CODE_LENGTH = 6
INVITE_EXPIRES_DAYS = 7
COMMENT_MAX_LENGTH = 160
# §11 "빈도를 제한한다"의 구체 값 — 운영 정책으로 확정되기 전까지의 권장 기본값.
NUDGE_COOLDOWN_SECONDS = 3600


class RoomError(Exception):
    """라우터가 그대로 §12 오류 응답({code, detail})으로 변환한다."""

    def __init__(self, status_code: int, code: str, detail: str):
        self.status_code = status_code
        self.code = code
        self.detail = detail
        super().__init__(detail)


def _not_found() -> RoomError:
    return RoomError(404, "ROOM_NOT_FOUND", "모임을 찾을 수 없어요.")


def _access_denied() -> RoomError:
    return RoomError(403, "ROOM_ACCESS_DENIED", "이 모임에 접근할 권한이 없어요.")


# ── 조회 ─────────────────────────────────────────────────────────────────────

async def get_room(db: AsyncSession, room_id: uuid.UUID) -> Room:
    room = await db.get(Room, room_id)
    if room is None or room.deleted_at is not None:
        raise _not_found()
    return room


async def get_membership(db: AsyncSession, room_id: uuid.UUID, user_id: int) -> RoomMember | None:
    result = await db.execute(
        select(RoomMember).where(
            RoomMember.room_id == room_id, RoomMember.user_id == user_id, RoomMember.left_at.is_(None)
        )
    )
    return result.scalar_one_or_none()


async def require_membership(db: AsyncSession, room_id: uuid.UUID, user_id: int) -> RoomMember:
    membership = await get_membership(db, room_id, user_id)
    if membership is None:
        raise _access_denied()
    return membership


async def list_active_members(db: AsyncSession, room_id: uuid.UUID) -> list[RoomMember]:
    # 정렬: 방장 우선, joined_at, user_id — §10 권장 기준.
    result = await db.execute(
        select(RoomMember)
        .where(RoomMember.room_id == room_id, RoomMember.left_at.is_(None))
        .order_by((RoomMember.role != "owner"), RoomMember.joined_at, RoomMember.user_id)
    )
    return list(result.scalars().all())


async def list_rooms_for_user(db: AsyncSession, user_id: int) -> list[tuple[Room, RoomMember]]:
    result = await db.execute(
        select(Room, RoomMember)
        .join(RoomMember, RoomMember.room_id == Room.id)
        .where(RoomMember.user_id == user_id, RoomMember.left_at.is_(None), Room.deleted_at.is_(None))
        .order_by(Room.created_at.desc())
    )
    return list(result.all())


async def get_display_names_bulk(db: AsyncSession, user_ids: list[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    ids = set(user_ids)
    result = await db.execute(select(UserRef).where(UserRef.id.in_(ids)))
    names: dict[int, str] = {}
    missing: list[int] = []
    for u in result.scalars().all():
        if u.display_name:
            names[u.id] = u.display_name
        else:
            missing.append(u.id)

    # users.display_name은 마이페이지에서 직접 이름을 바꾼 경우에만 채워진다 -
    # 그 전까지는 login-service 자신도 소셜 로그인 시점의 provider nickname으로
    # 폴백한다(app/routers/user.py의 동일 로직). 여기서 이 폴백을 안 타서,
    # 이름을 한 번도 안 바꾼 대부분의 멤버가 전부 "회원{id}"로만 보이던 버그
    # (2026-07-26 실사용 중 재현 - 그룹장만 정상, 나머지는 전부 회원n).
    if missing:
        social_result = await db.execute(
            select(SocialAccountRef)
            .where(SocialAccountRef.user_id.in_(missing))
            .order_by(SocialAccountRef.id)
        )
        for account in social_result.scalars().all():
            names.setdefault(account.user_id, account.nickname)

    return names


def avatar_text(display_name: str) -> str:
    stripped = display_name.strip()
    return stripped[:2] if stripped else "?"


def compute_permissions(room: Room, membership: RoomMember, active_member_count: int) -> dict[str, bool]:
    is_owner = membership.role == "owner"
    return {
        "canEditRoom": is_owner,
        "canInvite": True,
        "canManageMembers": is_owner,
        "canTransferOwnership": is_owner and active_member_count > 1,
        "canDeleteRoom": is_owner,
        # §5 "방장은 다른 활성 멤버가 있으면 위임 전까지 canLeaveRoom=false".
        "canLeaveRoom": (not is_owner) or active_member_count == 1,
    }


# ── 생성/참여 (3개 제한은 advisory lock으로 원자성 보장) ───────────────────────

async def _count_active_rooms(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(RoomMember)
        .join(Room, Room.id == RoomMember.room_id)
        .where(RoomMember.user_id == user_id, RoomMember.left_at.is_(None), Room.deleted_at.is_(None))
    )
    return result.scalar_one()


async def create_room(db: AsyncSession, owner_id: int, name: str, emoji: str, ranking_opt_in: bool) -> Room:
    # pg_advisory_xact_lock: 같은 user_id로 동시에 두 번 생성/참여 요청이 들어와도
    # "3개 이하인지 확인 → insert"가 한 트랜잭션씩 순서대로만 실행되게 직렬화한다.
    # 트랜잭션 커밋/롤백 시 자동 해제되므로 별도 unlock이 필요 없다.
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": owner_id})

    if await _count_active_rooms(db, owner_id) >= MAX_ROOM_COUNT:
        raise RoomError(409, "ROOM_LIMIT_EXCEEDED", "얌로그 모임은 3개까지 함께할 수 있어요.")

    room = Room(id=uuid.uuid4(), name=name, emoji=emoji, owner_id=owner_id, ranking_opt_in=ranking_opt_in)
    db.add(room)
    await db.flush()

    db.add(RoomMember(room_id=room.id, user_id=owner_id, role="owner"))
    await db.commit()
    await db.refresh(room)
    return room


def _hash_invite_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _generate_invite_code() -> str:
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))


async def create_invite(db: AsyncSession, room_id: uuid.UUID, actor_id: int) -> tuple[RoomInvite, str]:
    await require_owner(db, room_id, actor_id)

    # "새 코드 발급 시 기존 활성 코드는 즉시 무효화"
    result = await db.execute(
        select(RoomInvite).where(RoomInvite.room_id == room_id, RoomInvite.revoked_at.is_(None))
    )
    for existing in result.scalars().all():
        existing.revoked_at = datetime.now(timezone.utc)

    # DB unique(code_hash)와 충돌하면(사실상 불가능에 가까운 해시 충돌) 재시도.
    for _ in range(5):
        code = _generate_invite_code()
        code_hash = _hash_invite_code(code)
        exists = await db.execute(select(RoomInvite.id).where(RoomInvite.code_hash == code_hash))
        if exists.scalar_one_or_none() is None:
            break
    else:
        raise RoomError(500, "INVITE_GENERATION_FAILED", "초대 코드 생성에 실패했어요. 다시 시도해주세요.")

    invite = RoomInvite(
        id=uuid.uuid4(),
        room_id=room_id,
        code_hash=code_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRES_DAYS),
        created_by=actor_id,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite, code


async def get_active_invite(db: AsyncSession, room_id: uuid.UUID, actor_id: int) -> RoomInvite | None:
    await require_owner(db, room_id, actor_id)
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(RoomInvite)
        .where(RoomInvite.room_id == room_id, RoomInvite.revoked_at.is_(None), RoomInvite.expires_at > now)
        .order_by(RoomInvite.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def revoke_invite(db: AsyncSession, room_id: uuid.UUID, actor_id: int) -> None:
    """활성 초대 코드를 새로 발급하지 않고 그냥 없앤다 - create_invite("새 코드
    만들기")와 달리 "코드 지우기"는 당장 아무도 새로 못 들어오게만 하고 싶을
    때 쓴다."""
    await require_owner(db, room_id, actor_id)
    result = await db.execute(
        select(RoomInvite).where(RoomInvite.room_id == room_id, RoomInvite.revoked_at.is_(None))
    )
    now = datetime.now(timezone.utc)
    for existing in result.scalars().all():
        existing.revoked_at = now
    await db.commit()


async def _get_invite_by_code(db: AsyncSession, code: str) -> RoomInvite | None:
    result = await db.execute(select(RoomInvite).where(RoomInvite.code_hash == _hash_invite_code(code)))
    return result.scalar_one_or_none()


async def preview_join(db: AsyncSession, user_id: int, code: str) -> dict[str, object]:
    if not code or len(code) != INVITE_CODE_LENGTH:
        raise RoomError(400, "INVALID_INVITE_CODE", "초대 코드 형식이 올바르지 않아요.")

    invite = await _get_invite_by_code(db, code)
    now = datetime.now(timezone.utc)
    if invite is None or invite.revoked_at is not None or invite.expires_at <= now:
        raise RoomError(404, "INVITE_NOT_FOUND", "없거나 만료된 초대예요.")

    room = await get_room(db, invite.room_id)
    members = await list_active_members(db, room.id)

    already_joined = any(m.user_id == user_id for m in members)
    room_limit_hit = (not already_joined) and await _count_active_rooms(db, user_id) >= MAX_ROOM_COUNT
    blocked_reason = "already_joined" if already_joined else ("room_limit" if room_limit_hit else None)

    return {
        "room": {
            "id": str(room.id),
            "name": room.name,
            "emoji": room.emoji,
            "memberCount": len(members),
            "daysSinceStart": (now - room.started_at).days,
            "rank": None,
        },
        "activityInLastSevenDays": await _count_recent_activity(db, room.id, now),
        "inviteExpiresAt": invite.expires_at.isoformat(),
        "canJoin": blocked_reason is None,
        "blockedReason": blocked_reason,
    }


async def _count_recent_activity(db: AsyncSession, room_id: uuid.UUID, now: datetime) -> int:
    since = (now - timedelta(days=7)).date()
    result = await db.execute(
        select(func.count())
        .select_from(RoomMealThread)
        .where(RoomMealThread.room_id == room_id, RoomMealThread.record_date >= since)
    )
    return result.scalar_one()


async def join_room(db: AsyncSession, user_id: int, code: str) -> Room:
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": user_id})

    invite = await _get_invite_by_code(db, code)
    now = datetime.now(timezone.utc)
    if invite is None or invite.revoked_at is not None or invite.expires_at <= now:
        raise RoomError(404, "INVITE_NOT_FOUND", "없거나 만료된 초대예요.")

    room = await get_room(db, invite.room_id)

    existing = await get_membership(db, room.id, user_id)
    if existing is not None:
        raise RoomError(409, "ALREADY_JOINED", "이미 참여한 모임이에요.")

    if await _count_active_rooms(db, user_id) >= MAX_ROOM_COUNT:
        raise RoomError(409, "ROOM_LIMIT_EXCEEDED", "얌로그 모임은 3개까지 함께할 수 있어요.")

    # 예전에 나갔던 멤버가 다시 들어오는 경우 row가 이미 있을 수 있다(left_at IS
    # NOT NULL) — get_membership은 활성 멤버만 보므로 여기선 못 찾지만, PK가
    # (room_id, user_id)라 새로 add하면 충돌한다. 있으면 재활성화, 없으면 생성.
    stale = await db.get(RoomMember, {"room_id": room.id, "user_id": user_id})
    if stale is not None:
        stale.left_at = None
        stale.role = "member"
        stale.joined_at = now
    else:
        db.add(RoomMember(room_id=room.id, user_id=user_id, role="member", joined_at=now))

    await db.commit()
    await db.refresh(room)
    return room


# ── 방장/멤버 관리 ───────────────────────────────────────────────────────────

async def require_owner(db: AsyncSession, room_id: uuid.UUID, user_id: int) -> RoomMember:
    membership = await require_membership(db, room_id, user_id)
    if membership.role != "owner":
        raise _access_denied()
    return membership


async def update_room(
    db: AsyncSession, room_id: uuid.UUID, actor_id: int, *, name: str | None, emoji: str | None, ranking_opt_in: bool | None
) -> Room:
    await require_owner(db, room_id, actor_id)
    room = await get_room(db, room_id)
    if name is not None:
        room.name = name
    if emoji is not None:
        room.emoji = emoji
    if ranking_opt_in is not None:
        room.ranking_opt_in = ranking_opt_in
    room.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(room)
    return room


async def delete_room(db: AsyncSession, room_id: uuid.UUID, actor_id: int) -> None:
    await require_owner(db, room_id, actor_id)
    room = await get_room(db, room_id)
    room.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def leave_room(db: AsyncSession, room_id: uuid.UUID, user_id: int) -> None:
    membership = await require_membership(db, room_id, user_id)
    if membership.role == "owner":
        active_count = len(await list_active_members(db, room_id))
        if active_count > 1:
            raise RoomError(403, "OWNER_CANNOT_LEAVE", "방장은 다른 멤버에게 방장을 넘긴 뒤 탈퇴할 수 있어요.")
        # 마지막 남은 멤버(방장 본인)면 탈퇴 = 사실상 모임이 비므로 같이 정리.
        room = await get_room(db, room_id)
        room.deleted_at = datetime.now(timezone.utc)
    membership.left_at = datetime.now(timezone.utc)
    await db.commit()


async def remove_member(db: AsyncSession, room_id: uuid.UUID, actor_id: int, target_user_id: int) -> None:
    await require_owner(db, room_id, actor_id)
    if actor_id == target_user_id:
        raise RoomError(403, "OWNER_CANNOT_LEAVE", "방장 스스로를 내보낼 수 없어요. 탈퇴하려면 방장을 위임하세요.")
    target = await get_membership(db, room_id, target_user_id)
    if target is None:
        raise _not_found()
    target.left_at = datetime.now(timezone.utc)
    await db.commit()


async def transfer_ownership(db: AsyncSession, room_id: uuid.UUID, actor_id: int, target_user_id: int) -> None:
    owner_membership = await require_owner(db, room_id, actor_id)
    target = await get_membership(db, room_id, target_user_id)
    if target is None:
        raise RoomError(404, "ROOM_NOT_FOUND", "대상 멤버를 찾을 수 없어요.")

    room = await get_room(db, room_id)
    owner_membership.role = "member"
    target.role = "owner"
    room.owner_id = target_user_id
    await db.commit()


async def update_notifications(
    db: AsyncSession, room_id: uuid.UUID, user_id: int, *, nudges: bool, comments_and_reactions: bool
) -> RoomMember:
    membership = await require_membership(db, room_id, user_id)
    membership.nudge_notifications = nudges
    membership.activity_notifications = comments_and_reactions
    await db.commit()
    await db.refresh(membership)
    return membership


# ── 식단 스레드 / 댓글 / 반응 ─────────────────────────────────────────────────

async def get_or_create_thread(
    db: AsyncSession, room_id: uuid.UUID, user_id: int, record_date: date, meal_type: str
) -> RoomMealThread:
    result = await db.execute(
        select(RoomMealThread).where(
            RoomMealThread.room_id == room_id,
            RoomMealThread.user_id == user_id,
            RoomMealThread.record_date == record_date,
            RoomMealThread.meal_type == meal_type,
        )
    )
    thread = result.scalar_one_or_none()
    if thread is not None:
        return thread

    thread = RoomMealThread(room_id=room_id, user_id=user_id, record_date=record_date, meal_type=meal_type)
    db.add(thread)
    try:
        await db.flush()
        # flush()는 같은 트랜잭션 안에서만 보이게 할 뿐 실제로 커밋하지
        # 않는다 - get_db()가 요청 끝에 별도 commit 없이 세션을 닫기
        # 때문에(app/core/database.py), 여기서 커밋을 안 하면 방 상세를
        # 열거나 diet-service 웹훅을 받아 스레드를 만들어도 그 요청이
        # 끝나는 순간 통째로 롤백돼 DB에 전혀 안 남았다(2026-07-30
        # 리포트: 방금 올린 사진이 얌로그 홈에 영영 안 뜨는 문제의 원인).
        await db.commit()
    except Exception:
        # 동시에 두 요청이 같은 조합으로 get-or-create 하다 unique 제약에
        # 걸리면, 롤백 후 이미 만들어진 걸 다시 읽어온다.
        await db.rollback()
        result = await db.execute(
            select(RoomMealThread).where(
                RoomMealThread.room_id == room_id,
                RoomMealThread.user_id == user_id,
                RoomMealThread.record_date == record_date,
                RoomMealThread.meal_type == meal_type,
            )
        )
        thread = result.scalar_one_or_none()
        if thread is None:
            raise
    return thread


async def get_thread(db: AsyncSession, room_id: uuid.UUID, thread_id: uuid.UUID) -> RoomMealThread:
    thread = await db.get(RoomMealThread, thread_id)
    if thread is None or thread.room_id != room_id:
        raise RoomError(404, "ROOM_NOT_FOUND", "식사 기록을 찾을 수 없어요.")
    return thread


async def list_comments(
    db: AsyncSession, thread_id: uuid.UUID, cursor: str | None, limit: int = 20
) -> tuple[list[RoomMealComment], str | None]:
    stmt = select(RoomMealComment).where(
        RoomMealComment.thread_id == thread_id, RoomMealComment.deleted_at.is_(None)
    )
    if cursor:
        try:
            cursor_created_at = datetime.fromisoformat(cursor)
        except ValueError:
            raise RoomError(400, "INVALID_CURSOR", "cursor 형식이 올바르지 않아요.")
        stmt = stmt.where(RoomMealComment.created_at < cursor_created_at)
    stmt = stmt.order_by(RoomMealComment.created_at.desc()).limit(limit + 1)

    rows = list((await db.execute(stmt)).scalars().all())
    next_cursor = rows[limit].created_at.isoformat() if len(rows) > limit else None
    return rows[:limit], next_cursor


async def add_comment(db: AsyncSession, thread_id: uuid.UUID, author_id: int, message: str) -> RoomMealComment:
    trimmed = message.strip()
    if not trimmed:
        raise RoomError(422, "INVALID_COMMENT", "댓글 내용을 입력해주세요.")
    if len(trimmed) > COMMENT_MAX_LENGTH:
        raise RoomError(422, "INVALID_COMMENT", f"댓글은 {COMMENT_MAX_LENGTH}자 이하로 입력해주세요.")

    comment = RoomMealComment(id=uuid.uuid4(), thread_id=thread_id, author_id=author_id, message=trimmed)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


async def delete_comment(db: AsyncSession, comment_id: uuid.UUID, user_id: int) -> None:
    comment = await db.get(RoomMealComment, comment_id)
    if comment is None or comment.deleted_at is not None:
        raise RoomError(404, "ROOM_NOT_FOUND", "댓글을 찾을 수 없어요.")
    if comment.author_id != user_id:
        raise _access_denied()
    comment.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def count_comments(db: AsyncSession, thread_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(RoomMealComment)
        .where(RoomMealComment.thread_id == thread_id, RoomMealComment.deleted_at.is_(None))
    )
    return result.scalar_one()


async def toggle_reaction(db: AsyncSession, thread_id: uuid.UUID, user_id: int) -> tuple[bool, int]:
    existing = await db.get(RoomMealReaction, {"thread_id": thread_id, "user_id": user_id})
    if existing is not None:
        await db.delete(existing)
        reacted = False
    else:
        db.add(RoomMealReaction(thread_id=thread_id, user_id=user_id))
        reacted = True
    await db.commit()

    count_result = await db.execute(
        select(func.count()).select_from(RoomMealReaction).where(RoomMealReaction.thread_id == thread_id)
    )
    return reacted, count_result.scalar_one()


async def count_reactions(db: AsyncSession, thread_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(RoomMealReaction).where(RoomMealReaction.thread_id == thread_id)
    )
    return result.scalar_one()


async def has_reacted(db: AsyncSession, thread_id: uuid.UUID, user_id: int) -> bool:
    existing = await db.get(RoomMealReaction, {"thread_id": thread_id, "user_id": user_id})
    return existing is not None


# ── 콕 찌르기 ────────────────────────────────────────────────────────────────

async def send_nudge(
    db: AsyncSession, room_id: uuid.UUID, sender_id: int, target_user_id: int, record_date: date, meal_type: str
) -> None:
    await require_membership(db, room_id, sender_id)
    if sender_id == target_user_id:
        raise RoomError(422, "CANNOT_NUDGE_SELF", "본인은 콕 찌를 수 없어요.")
    target = await get_membership(db, room_id, target_user_id)
    if target is None:
        raise RoomError(404, "ROOM_NOT_FOUND", "대상 멤버를 찾을 수 없어요.")

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(RoomNudge)
        .where(
            RoomNudge.room_id == room_id,
            RoomNudge.target_user_id == target_user_id,
            RoomNudge.sender_id == sender_id,
            RoomNudge.record_date == record_date,
            RoomNudge.meal_type == meal_type,
        )
        .order_by(RoomNudge.created_at.desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    if last is not None:
        elapsed = (now - last.created_at).total_seconds()
        if elapsed < NUDGE_COOLDOWN_SECONDS:
            retry_after = int(NUDGE_COOLDOWN_SECONDS - elapsed)
            raise RoomError(429, "NUDGE_RATE_LIMITED", f"{retry_after}초 후에 다시 찔러볼 수 있어요.")

    db.add(RoomNudge(
        room_id=room_id, target_user_id=target_user_id, sender_id=sender_id,
        record_date=record_date, meal_type=meal_type,
    ))
    await db.commit()


async def get_last_nudge(
    db: AsyncSession, room_id: uuid.UUID, sender_id: int, target_user_id: int, record_date: date, meal_type: str
) -> RoomNudge | None:
    result = await db.execute(
        select(RoomNudge)
        .where(
            RoomNudge.room_id == room_id,
            RoomNudge.target_user_id == target_user_id,
            RoomNudge.sender_id == sender_id,
            RoomNudge.record_date == record_date,
            RoomNudge.meal_type == meal_type,
        )
        .order_by(RoomNudge.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_incoming_nudges(
    db: AsyncSession, target_user_id: int, room_id: uuid.UUID | None = None
) -> list[RoomNudge]:
    """받는 사람이 아직 못 본 콕 찌르기 목록. 이 서비스엔 실시간 푸시가 없어서
    (폴링 방식), 방/홈 화면을 열 때 이 목록을 보여주고 acknowledge_nudges로
    확인 처리한다. nudge_notifications를 꺼둔 멤버십은 제외한다(§11)."""
    stmt = (
        select(RoomNudge)
        .join(
            RoomMember,
            (RoomMember.room_id == RoomNudge.room_id) & (RoomMember.user_id == RoomNudge.target_user_id),
        )
        .where(
            RoomNudge.target_user_id == target_user_id,
            RoomNudge.acknowledged_at.is_(None),
            RoomMember.left_at.is_(None),
            RoomMember.nudge_notifications.is_(True),
        )
    )
    if room_id is not None:
        stmt = stmt.where(RoomNudge.room_id == room_id)
    stmt = stmt.order_by(RoomNudge.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def acknowledge_nudges(db: AsyncSession, nudge_ids: list[uuid.UUID]) -> None:
    if not nudge_ids:
        return
    now = datetime.now(timezone.utc)
    await db.execute(
        RoomNudge.__table__.update().where(RoomNudge.id.in_(nudge_ids)).values(acknowledged_at=now)
    )
    await db.commit()


# ── 신고 ─────────────────────────────────────────────────────────────────────

async def report_content(
    db: AsyncSession, room_id: uuid.UUID, reporter_id: int, target_type: str, target_id: str, reason: str
) -> None:
    await require_membership(db, room_id, reporter_id)
    if target_type not in ("meal", "comment"):
        raise RoomError(422, "INVALID_REPORT", "targetType이 올바르지 않아요.")
    if reason not in ("spam", "inappropriate", "privacy", "other"):
        raise RoomError(422, "INVALID_REPORT", "reason이 올바르지 않아요.")

    db.add(RoomReport(
        room_id=room_id, reporter_id=reporter_id, target_type=target_type, target_id=target_id, reason=reason,
    ))
    await db.commit()
