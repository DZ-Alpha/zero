import uuid
from datetime import date as date_cls
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import UserIdentity, require_room_user
from app.services import idempotency, room_aggregation, room_store
from app.services.room_store import RoomError

router = APIRouter(prefix="/rooms")


def _err(error: RoomError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail={"code": error.code, "detail": error.detail})


def _to_uuid(value: str, code: str = "ROOM_NOT_FOUND") -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": code, "detail": "찾을 수 없어요."})


def _to_user_id(member_id: str) -> int:
    try:
        return int(member_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "ROOM_NOT_FOUND", "detail": "멤버를 찾을 수 없어요."})


async def _idempotent(
    db: AsyncSession, user_id: int, idempotency_key: str | None, run,
) -> object:
    """§9 - 생성/참여/초대재발급/댓글/콕찌르기 공통 idempotency 처리.
    같은 키로 재요청되면 실제 처리를 다시 하지 않고 저장된 응답을 그대로
    돌려준다. 키가 없으면(예: 오래된 클라이언트) 그냥 매번 실행한다."""
    if idempotency_key:
        cached = await idempotency.get_cached(db, idempotency_key, user_id)
        if cached is not None:
            return cached

    try:
        body = await run()
    except RoomError as error:
        raise _err(error)

    if idempotency_key:
        await idempotency.store(db, idempotency_key, user_id, 200, body)
    return body


# ── 홈 ───────────────────────────────────────────────────────────────────────

@router.get("")
async def get_rooms_home(
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    my_rooms = await room_store.list_rooms_for_user(db, user.user_id)
    room_by_id = {room.id: room for room, _membership in my_rooms}
    summaries = []
    for room, membership in my_rooms:
        summary = await room_aggregation.compute_room_summary(db, room, membership, user.user_id)
        summaries.append(summary)

    activities, activities_cursor = await room_aggregation.list_recent_activities(db, user.user_id, None, today_only=True)
    ranking, ranking_cursor = await room_aggregation.list_weekly_ranking(db, user.user_id, None)
    for index, entry in enumerate(ranking):
        entry["rank"] = index + 1
    incoming_nudges = await room_aggregation.build_incoming_nudges(db, user.user_id, room_by_id)

    return {
        "rooms": summaries,
        "recentActivities": activities,
        "weeklyRanking": ranking,
        "activeTeamCount": len(summaries),
        "maxRoomCount": room_store.MAX_ROOM_COUNT,
        "recentActivitiesNextCursor": activities_cursor,
        "weeklyRankingNextCursor": ranking_cursor,
        "incomingNudges": incoming_nudges,
    }


@router.get("/activities")
async def get_more_activities(
    cursor: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    try:
        items, next_cursor = await room_aggregation.list_recent_activities(db, user.user_id, cursor)
    except RoomError as error:
        raise _err(error)
    return {"recentActivities": items, "recentActivitiesNextCursor": next_cursor}


@router.get("/ranking")
async def get_more_ranking(
    cursor: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    try:
        items, next_cursor = await room_aggregation.list_weekly_ranking(db, user.user_id, cursor)
    except RoomError as error:
        raise _err(error)
    return {"weeklyRanking": items, "weeklyRankingNextCursor": next_cursor}


# ── 참여(리터럴 경로 - {room_id}보다 먼저 등록) ────────────────────────────────

class JoinRoomBody(BaseModel):
    code: str


@router.get("/join-preview")
async def get_join_preview(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    try:
        return await room_store.preview_join(db, user.user_id, code)
    except RoomError as error:
        raise _err(error)


@router.post("/join")
async def post_join_room(
    body: JoinRoomBody,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> dict[str, object]:
    async def run():
        room = await room_store.join_room(db, user.user_id, body.code)
        membership = await room_store.require_membership(db, room.id, user.user_id)
        return await _room_detail_payload(db, room.id, user.user_id, None, room=room, membership=membership)

    return await _idempotent(db, user.user_id, idempotency_key, run)


# ── 생성 ─────────────────────────────────────────────────────────────────────

class CreateRoomBody(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=24)]
    emoji: str
    rankingOptIn: bool = True


@router.post("")
async def post_create_room(
    body: CreateRoomBody,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> dict[str, object]:
    async def run():
        room = await room_store.create_room(db, user.user_id, body.name.strip(), body.emoji, body.rankingOptIn)
        membership = await room_store.require_membership(db, room.id, user.user_id)
        summary = await room_aggregation.compute_room_summary(db, room, membership, user.user_id)
        summary["averageSugar"] = 0.0
        invite, code = await room_store.create_invite(db, room.id, user.user_id)
        return {
            "room": summary,
            "invite": {
                "code": code,
                "joinUrl": f"/rooms/join?code={code}",
                "expiresAt": invite.expires_at.isoformat(),
            },
        }

    return await _idempotent(db, user.user_id, idempotency_key, run)


# ── 상세/설정 ────────────────────────────────────────────────────────────────

async def _room_detail_payload(
    db: AsyncSession, room_id: uuid.UUID, viewer_id: int, date_str: str | None, *, room=None, membership=None,
) -> dict[str, object]:
    if room is None:
        room = await room_store.get_room(db, room_id)
    if membership is None:
        membership = await room_store.require_membership(db, room_id, viewer_id)

    summary = await room_aggregation.compute_room_summary(db, room, membership, viewer_id)

    members = await room_store.list_active_members(db, room_id)
    member_list = await room_aggregation.build_room_members(db, room, members, viewer_id)

    target_date = date_cls.fromisoformat(date_str) if date_str else room_aggregation.today_kst()
    slots = await room_aggregation.build_meal_slots(db, room_id, members, target_date, viewer_id)
    today = room_aggregation.today_kst()
    badges = await room_aggregation.build_room_badges(db, room_id, members, today)
    incoming_nudges = await room_aggregation.build_incoming_nudges(db, viewer_id, {room_id: room}, room_id)

    return {
        "room": summary,
        "members": member_list,
        "serverDate": today.isoformat(),
        "timezone": "Asia/Seoul",
        "todayMealSlots": slots,
        "badges": badges,
        "incomingNudges": incoming_nudges,
    }


@router.get("/{room_id}")
async def get_room_detail(
    room_id: str,
    date: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    rid = _to_uuid(room_id)
    try:
        return await _room_detail_payload(db, rid, user.user_id, date)
    except RoomError as error:
        raise _err(error)


class UpdateRoomBody(BaseModel):
    name: str | None = None
    emoji: str | None = None
    rankingOptIn: bool | None = None
    memberInviteEnabled: bool | None = None


@router.patch("/{room_id}")
async def patch_room(
    room_id: str,
    body: UpdateRoomBody,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    rid = _to_uuid(room_id)
    try:
        await room_store.update_room(
            db, rid, user.user_id,
            name=body.name, emoji=body.emoji, ranking_opt_in=body.rankingOptIn,
            member_invite_enabled=body.memberInviteEnabled,
        )
        return await _get_settings_payload(db, rid, user.user_id)
    except RoomError as error:
        raise _err(error)


@router.delete("/{room_id}")
async def delete_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, str]:
    rid = _to_uuid(room_id)
    try:
        await room_store.delete_room(db, rid, user.user_id)
    except RoomError as error:
        raise _err(error)
    return {"status": "deleted"}


async def _get_settings_payload(db: AsyncSession, room_id: uuid.UUID, viewer_id: int) -> dict[str, object]:
    room = await room_store.get_room(db, room_id)
    membership = await room_store.require_membership(db, room_id, viewer_id)
    summary = await room_aggregation.compute_room_summary(db, room, membership, viewer_id)

    members = await room_store.list_active_members(db, room_id)
    member_list = await room_aggregation.build_room_members(db, room, members, viewer_id)

    # 2026-07-30 요청 - 초대 코드 열람도 canInvite와 같은 기준(방장, 또는
    # 방장이 member_invite_enabled를 켠 경우의 멤버)을 따른다 - 하드코딩된
    # "방장만" 조건을 없애 권한이 하나로 일원화되게 한다.
    active_invite = None
    if summary["permissions"]["canInvite"]:
        invite = await room_store.get_active_invite(db, room_id, viewer_id)
        if invite is not None:
            active_invite = {"code": None, "joinUrl": None, "expiresAt": invite.expires_at.isoformat()}

    return {
        "room": summary,
        "notifications": {
            "nudges": membership.nudge_notifications,
            "commentsAndReactions": membership.activity_notifications,
        },
        "memberInviteEnabled": await room_store.get_member_invite_enabled(db, room_id),
        "activeInvite": active_invite,
        "members": member_list,
    }


@router.get("/{room_id}/settings")
async def get_room_settings(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    rid = _to_uuid(room_id)
    try:
        return await _get_settings_payload(db, rid, user.user_id)
    except RoomError as error:
        raise _err(error)


# ── 초대 ─────────────────────────────────────────────────────────────────────

@router.get("/{room_id}/invite")
async def get_invite(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    rid = _to_uuid(room_id)
    try:
        invite = await room_store.get_active_invite(db, rid, user.user_id)
    except RoomError as error:
        raise _err(error)
    if invite is None:
        raise HTTPException(status_code=404, detail={"code": "INVITE_NOT_FOUND", "detail": "활성 초대가 없어요."})
    # 코드 원문은 저장하지 않으므로(해시만 보관) 재조회 시엔 내려줄 수 없다 -
    # 프론트는 만료시각/링크 유효성 확인 용도로만 이 응답을 쓰고, 코드 자체가
    # 다시 필요하면(예: 공유하기 버튼) POST로 재발급해야 한다.
    return {"code": None, "joinUrl": None, "expiresAt": invite.expires_at.isoformat()}


@router.post("/{room_id}/invite")
async def post_regenerate_invite(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> dict[str, object]:
    rid = _to_uuid(room_id)

    async def run():
        invite, code = await room_store.create_invite(db, rid, user.user_id)
        return {"code": code, "joinUrl": f"/rooms/join?code={code}", "expiresAt": invite.expires_at.isoformat()}

    return await _idempotent(db, user.user_id, idempotency_key, run)


@router.delete("/{room_id}/invite")
async def delete_invite(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    rid = _to_uuid(room_id)
    try:
        await room_store.revoke_invite(db, rid, user.user_id)
    except RoomError as error:
        raise _err(error)
    return {"status": "deleted"}


# ── 멤버십 ───────────────────────────────────────────────────────────────────

@router.delete("/{room_id}/membership")
async def delete_membership(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, str]:
    rid = _to_uuid(room_id)
    try:
        await room_store.leave_room(db, rid, user.user_id)
    except RoomError as error:
        raise _err(error)
    return {"status": "left"}


class UpdateNotificationsBody(BaseModel):
    nudges: bool
    commentsAndReactions: bool


@router.patch("/{room_id}/notifications")
async def patch_notifications(
    room_id: str,
    body: UpdateNotificationsBody,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    rid = _to_uuid(room_id)
    try:
        await room_store.update_notifications(
            db, rid, user.user_id, nudges=body.nudges, comments_and_reactions=body.commentsAndReactions
        )
    except RoomError as error:
        raise _err(error)
    return {"nudges": body.nudges, "commentsAndReactions": body.commentsAndReactions}


@router.put("/{room_id}/members/{member_id}/ownership")
async def put_transfer_ownership(
    room_id: str,
    member_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, str]:
    rid = _to_uuid(room_id)
    target_id = _to_user_id(member_id)
    try:
        await room_store.transfer_ownership(db, rid, user.user_id, target_id)
    except RoomError as error:
        raise _err(error)
    return {"status": "transferred"}


@router.delete("/{room_id}/members/{member_id}")
async def delete_member(
    room_id: str,
    member_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, str]:
    rid = _to_uuid(room_id)
    target_id = _to_user_id(member_id)
    try:
        await room_store.remove_member(db, rid, user.user_id, target_id)
    except RoomError as error:
        raise _err(error)
    return {"status": "removed"}


@router.get("/{room_id}/members/{member_id}/calendar")
async def get_member_calendar(
    room_id: str,
    member_id: str,
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    rid = _to_uuid(room_id)
    target_id = _to_user_id(member_id)
    try:
        await room_store.require_membership(db, rid, user.user_id)
    except RoomError as error:
        raise _err(error)
    days = await room_aggregation.build_member_calendar(db, rid, target_id, year, month)
    return {"days": days}


@router.get("/{room_id}/calendar")
async def get_room_calendar(
    room_id: str,
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    """방 전체 월간 캘린더 - 날짜별 기록 수와 그중 내 기록 수. 방 상세의
    과거 날짜 이동(캘린더) UI가 "나도 올린 날/남만 올린 날"을 색으로
    구분하는 데 쓴다."""
    rid = _to_uuid(room_id)
    try:
        await room_store.require_membership(db, rid, user.user_id)
    except RoomError as error:
        raise _err(error)
    days = await room_aggregation.build_room_calendar(db, rid, user.user_id, year, month)
    return {"days": days}


# ── 콕 찌르기 ────────────────────────────────────────────────────────────────

class NudgeBody(BaseModel):
    memberId: str
    mealType: str


@router.post("/{room_id}/nudges")
async def post_nudge(
    room_id: str,
    body: NudgeBody,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> dict[str, object]:
    rid = _to_uuid(room_id)
    target_id = _to_user_id(body.memberId)
    meal_type_db = room_aggregation.to_db_meal_type(body.mealType)
    today = room_aggregation.today_kst()

    async def run():
        await room_store.send_nudge(db, rid, user.user_id, target_id, today, meal_type_db)
        return {"status": "sent", "retryAfterSeconds": room_store.NUDGE_COOLDOWN_SECONDS}

    return await _idempotent(db, user.user_id, idempotency_key, run)


# ── 댓글/반응 ────────────────────────────────────────────────────────────────

def _comment_dict(comment, viewer_id: int, display_name: str) -> dict[str, object]:
    return {
        "id": str(comment.id),
        "authorId": str(comment.author_id),
        "authorName": display_name,
        "message": comment.message,
        "createdAt": comment.created_at.isoformat(),
        "canDelete": comment.author_id == viewer_id,
    }


@router.get("/{room_id}/meals/{meal_id}/comments")
async def get_meal_comments(
    room_id: str,
    meal_id: str,
    cursor: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    rid = _to_uuid(room_id)
    tid = _to_uuid(meal_id)
    try:
        await room_store.require_membership(db, rid, user.user_id)
        await room_store.get_thread(db, rid, tid)
        comments, next_cursor = await room_store.list_comments(db, tid, cursor)
    except RoomError as error:
        raise _err(error)

    names = await room_store.get_display_names_bulk(db, [c.author_id for c in comments])
    items = [_comment_dict(c, user.user_id, names.get(c.author_id, f"회원{c.author_id}")) for c in comments]
    return {"items": items, "nextCursor": next_cursor}


class AddCommentBody(BaseModel):
    message: str


@router.post("/{room_id}/meals/{meal_id}/comments")
async def post_meal_comment(
    room_id: str,
    meal_id: str,
    body: AddCommentBody,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> dict[str, object]:
    rid = _to_uuid(room_id)
    tid = _to_uuid(meal_id)

    async def run():
        await room_store.require_membership(db, rid, user.user_id)
        await room_store.get_thread(db, rid, tid)
        comment = await room_store.add_comment(db, tid, user.user_id, body.message)
        names = await room_store.get_display_names_bulk(db, [user.user_id])
        return _comment_dict(comment, user.user_id, names.get(user.user_id, f"회원{user.user_id}"))

    return await _idempotent(db, user.user_id, idempotency_key, run)


@router.delete("/{room_id}/meals/{meal_id}/comments/{comment_id}")
async def delete_meal_comment(
    room_id: str,
    meal_id: str,
    comment_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, str]:
    _to_uuid(room_id)
    _to_uuid(meal_id)
    cid = _to_uuid(comment_id)
    try:
        await room_store.delete_comment(db, cid, user.user_id)
    except RoomError as error:
        raise _err(error)
    return {"status": "deleted"}


@router.put("/{room_id}/meals/{meal_id}/reaction")
async def put_meal_reaction(
    room_id: str,
    meal_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, object]:
    rid = _to_uuid(room_id)
    tid = _to_uuid(meal_id)
    try:
        await room_store.require_membership(db, rid, user.user_id)
        await room_store.get_thread(db, rid, tid)
        reacted, count = await room_store.toggle_reaction(db, tid, user.user_id)
    except RoomError as error:
        raise _err(error)
    return {"reacted": reacted, "reactionCount": count}


# ── 신고 ─────────────────────────────────────────────────────────────────────

class ReportBody(BaseModel):
    targetType: str
    targetId: str
    reason: str


@router.post("/{room_id}/reports")
async def post_report(
    room_id: str,
    body: ReportBody,
    db: AsyncSession = Depends(get_db),
    user: UserIdentity = Depends(require_room_user),
) -> dict[str, str]:
    rid = _to_uuid(room_id)
    try:
        await room_store.report_content(db, rid, user.user_id, body.targetType, body.targetId, body.reason)
    except RoomError as error:
        raise _err(error)
    return {"status": "received"}


# ── diet-service 전용 내부 알림 ────────────────────────────────────────────────
# room_meal_thread는 원래 방 화면 조회 시점(build_meal_slots)에만 lazy하게
# 생겼다 - 그래서 아무도 방을 열어보지 않으면 실제로 식단을 기록해도 얌로그
# 활동 피드/알림에 전혀 안 잡히는 문제가 있었다(팀원이 기록해도 방장이 방을
# 안 열어보면 감감무소식). diet-service가 식단 기록을 실제로 완료하는 시점에
# (Vision 분석 완료/사용자 확정/레시피·저당픽 직접 등록) 이 엔드포인트를 호출해서,
# 그 유저가 속한 모든 방에 해당 날짜/끼니 스레드를 그 자리에서 만들어둔다.

def _verify_internal_secret(x_internal_service_secret: str | None) -> None:
    # diet-service의 _verify_internal_secret과 동일한 이유 - 빈 값이면 무조건
    # 거부한다(설정 누락이 "누구나 통과"로 이어지지 않게).
    if not settings.internal_service_secret or x_internal_service_secret != settings.internal_service_secret:
        raise HTTPException(status_code=403, detail="internal service 인증에 실패했습니다.")


class NotifyMealRecordedBody(BaseModel):
    userId: int
    recordDate: str  # YYYY-MM-DD, Asia/Seoul 기준(diet-service가 이미 그 기준으로 계산해서 보낸다)
    mealType: str  # BREAKFAST | LUNCH | DINNER | SNACK


@router.post("/internal/meal-recorded")
async def notify_meal_recorded(
    body: NotifyMealRecordedBody,
    db: AsyncSession = Depends(get_db),
    x_internal_service_secret: str | None = Header(None),
) -> dict[str, object]:
    _verify_internal_secret(x_internal_service_secret)

    try:
        record_date = date_cls.fromisoformat(body.recordDate[:10])
    except ValueError:
        raise HTTPException(status_code=422, detail="recordDate 형식이 올바르지 않습니다 (YYYY-MM-DD).")

    meal_type = body.mealType.upper()
    if meal_type not in ("BREAKFAST", "LUNCH", "DINNER", "SNACK"):
        raise HTTPException(status_code=422, detail=f"mealType이 올바르지 않습니다: {body.mealType}")

    rooms = await room_store.list_rooms_for_user(db, body.userId)
    created_room_ids = []
    for room, _membership in rooms:
        await room_store.get_or_create_thread(db, room.id, body.userId, record_date, meal_type)
        created_room_ids.append(str(room.id))

    return {"status": "OK", "roomIds": created_room_ids}
