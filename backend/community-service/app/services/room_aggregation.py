"""얌로그 문서 §8(랭킹/현황 집계)의 정책 항목 중 아직 확정 안 된 것들은
문서가 제시한 권장값을 그대로 쓴다:
  - 시간대: Asia/Seoul
  - 주간: 월요일 00:00 ~ 일요일 23:59:59
  - 기록률 분모: 해당 기간의 활성 멤버 수 × 대상 끼니 수(4: 아침/점심/저녁/간식)
  - 동률 처리, 탈퇴 멤버 과거 기록 포함 여부, 재집계 시점, 캐시 갱신 주기는
    아직 정책이 없어 이 모듈에서 다루지 않는다 - 캐싱 없이 매 요청 즉시
    계산한다(정확하지만 방/사용자가 많아지면 느려질 수 있음 - 정책이 정해지면
    그때 캐시 레이어를 붙인다).
  - 팀 랭킹의 rankMovement(순위 변동)는 과거 주간 랭킹 스냅샷을 저장하는
    배치가 아직 없어서 항상 0을 반환한다 - 실제 변동 추적은 후속 작업이다
    (거짓으로 그럴듯한 값을 만들지 않기 위함).
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.room import Room
from app.models.room_member import RoomMember
from app.models.room_meal_thread import RoomMealThread
from app.services import room_store
from app.services.diet_client import get_meal_records

_KST = ZoneInfo("Asia/Seoul")
MEAL_TYPES_UPPER = ["BREAKFAST", "LUNCH", "DINNER", "SNACK"]
_TO_FRONTEND_MEAL_TYPE = {"BREAKFAST": "breakfast", "LUNCH": "lunch", "DINNER": "dinner", "SNACK": "snack"}
_TO_DB_MEAL_TYPE = {v: k for k, v in _TO_FRONTEND_MEAL_TYPE.items()}


def today_kst() -> date:
    return datetime.now(_KST).date()


def week_range_kst(today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=6)


def to_frontend_meal_type(value: str) -> str:
    return _TO_FRONTEND_MEAL_TYPE.get(value, value.lower())


def to_db_meal_type(value: str) -> str:
    mapped = _TO_DB_MEAL_TYPE.get(value.lower())
    if mapped is None:
        raise room_store.RoomError(422, "INVALID_MEAL_TYPE", f"mealType이 올바르지 않아요: {value}")
    return mapped


async def _member_user_ids(members: list[RoomMember]) -> list[int]:
    return [m.user_id for m in members]


async def _record_counts_for_range(
    db: AsyncSession, room_id: uuid.UUID, user_ids: list[int], start: date, end: date
) -> dict[tuple[int, date, str], bool]:
    """이 방의 room_meal_threads로 "그 조합에 기록이 있었는지"를 빠르게 판단한다
    - diet-service를 매번 왕복하지 않고, 이미 한 번이라도 방 화면에서 조회되며
    get_or_create_thread로 생성된 스레드 존재 여부를 근사치로 쓴다. 정확한
    실시간 집계가 필요해지면(§8 재집계 시점 정책 확정 후) diet-service 원본을
    기간 조회하는 방식으로 바꿔야 한다."""
    result = await db.execute(
        select(RoomMealThread.user_id, RoomMealThread.record_date, RoomMealThread.meal_type).where(
            RoomMealThread.room_id == room_id,
            RoomMealThread.user_id.in_(user_ids),
            RoomMealThread.record_date >= start,
            RoomMealThread.record_date <= end,
        )
    )
    return {(row.user_id, row.record_date, row.meal_type): True for row in result.all()}


async def compute_room_summary(db: AsyncSession, room: Room, membership: RoomMember, viewer_id: int) -> dict[str, object]:
    members = await room_store.list_active_members(db, room.id)
    member_count = len(members)
    today = today_kst()
    days_since_start = max(0, (today - room.started_at.astimezone(_KST).date()).days)

    week_start, week_end = week_range_kst(today)
    week_days_elapsed = (min(today, week_end) - week_start).days + 1
    slot_target = member_count * len(MEAL_TYPES_UPPER) * max(week_days_elapsed, 1)

    user_ids = await _member_user_ids(members)
    thread_map = await _record_counts_for_range(db, room.id, user_ids, week_start, week_end)

    recorded_today = len({uid for (uid, d, _mt) in thread_map if d == today})
    week_record_count = len(thread_map)
    my_participation_days = len({d for (uid, d, _mt) in thread_map if uid == viewer_id})

    eligible = member_count >= 3 and days_since_start >= 7 and room.ranking_opt_in

    return {
        "id": str(room.id),
        "name": room.name,
        "emoji": room.emoji,
        "role": membership.role,
        "memberCount": member_count,
        "recordedTodayCount": recorded_today,
        "daysSinceStart": days_since_start,
        # 이번 주 기록 개수 대비 기록률(§8 권장 분모 - slot_target=0 방지).
        "averageSugar": 0.0,  # 아래 hydrate_room_summary_sugar에서 diet-service 조회 후 채움
        "monthlyRecordRate": round(week_record_count / slot_target * 100, 1) if slot_target else 0.0,
        "myParticipationDays": my_participation_days,
        "rankingOptIn": room.ranking_opt_in,
        "rank": None,
        "rankingEligibility": {
            "eligible": eligible,
            "missingMemberCount": max(0, 3 - member_count),
            "remainingDays": max(0, 7 - days_since_start),
        },
        "permissions": room_store.compute_permissions(room, membership, member_count),
    }


_MEMBER_COLORS = ["#F4A261", "#2A9D8F", "#E76F51", "#457B9D", "#8D5A97", "#A3B18A"]


def _color_for(user_id: int) -> str:
    return _MEMBER_COLORS[user_id % len(_MEMBER_COLORS)]


async def _streak_days(db: AsyncSession, room_id: uuid.UUID, user_id: int, today: date) -> int:
    """오늘부터 거슬러 올라가며 이 방에서 기록이 있었던 연속 일수.

    room_meal_threads는 그 (user, date, mealType) 조합이 방 화면에서 한 번이라도
    조회돼 get_or_create_thread를 거쳤을 때만 생긴다 - 즉 이 스트릭은 "얌로그
    화면에서 확인된 기록" 기준의 근사치다. 정확한 스트릭이 필요해지면
    diet-service 원본을 기간 조회해야 한다(§8 재집계 정책 확정 후 개선 대상).
    """
    result = await db.execute(
        select(RoomMealThread.record_date)
        .where(RoomMealThread.room_id == room_id, RoomMealThread.user_id == user_id)
        .distinct()
    )
    recorded_days = {row.record_date for row in result.all()}
    streak = 0
    cursor = today
    while cursor in recorded_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


async def build_room_members(db: AsyncSession, room: Room, members: list[RoomMember], viewer_id: int) -> list[dict[str, object]]:
    user_ids = [m.user_id for m in members]
    display_names = await room_store.get_display_names_bulk(db, user_ids)
    today = today_kst()
    week_start, week_end = week_range_kst(today)
    week_days_elapsed = (min(today, week_end) - week_start).days + 1
    thread_map = await _record_counts_for_range(db, room.id, user_ids, week_start, week_end)

    records_today = await get_meal_records(user_ids, today)
    sugar_today_by_user: dict[int, float] = {}
    for record in records_today:
        uid = record["userId"]
        sugar_today_by_user[uid] = sugar_today_by_user.get(uid, 0.0) + float(record.get("sugar", 0.0))

    result = []
    for member in members:
        name = display_names.get(member.user_id, f"회원{member.user_id}")
        week_record_count = sum(1 for (uid, _d, _mt) in thread_map if uid == member.user_id)
        record_rate = round(week_record_count / (len(MEAL_TYPES_UPPER) * max(week_days_elapsed, 1)) * 100, 1)
        result.append({
            "id": str(member.user_id),
            "name": name,
            "avatarText": room_store.avatar_text(name),
            "role": member.role,
            "isMe": member.user_id == viewer_id,
            "joinedDays": max(0, (today - member.joined_at.astimezone(_KST).date()).days),
            "recordCount": week_record_count,
            "recordRate": record_rate,
            "averageSugar": round(sugar_today_by_user.get(member.user_id, 0.0), 1),
            "streakDays": await _streak_days(db, room.id, member.user_id, today),
            "color": _color_for(member.user_id),
        })
    return result


async def list_recent_activities(
    db: AsyncSession, viewer_id: int, cursor: str | None, limit: int = 20
) -> tuple[list[dict[str, object]], str | None]:
    my_rooms = await room_store.list_rooms_for_user(db, viewer_id)
    room_by_id = {room.id: room for room, _membership in my_rooms}
    if not room_by_id:
        return [], None

    stmt = select(RoomMealThread).where(RoomMealThread.room_id.in_(room_by_id.keys()))
    if cursor:
        try:
            cursor_created_at = datetime.fromisoformat(cursor)
        except ValueError:
            raise room_store.RoomError(400, "INVALID_CURSOR", "cursor 형식이 올바르지 않아요.")
        stmt = stmt.where(RoomMealThread.created_at < cursor_created_at)
    stmt = stmt.order_by(RoomMealThread.created_at.desc()).limit(limit + 1)

    threads = list((await db.execute(stmt)).scalars().all())
    next_cursor = threads[limit].created_at.isoformat() if len(threads) > limit else None
    threads = threads[:limit]

    display_names = await room_store.get_display_names_bulk(db, [t.user_id for t in threads])

    # date별로 묶어서 diet-service 호출을 최소화한다.
    by_date: dict[date, list[RoomMealThread]] = {}
    for thread in threads:
        by_date.setdefault(thread.record_date, []).append(thread)

    record_lookup: dict[tuple[int, str, date], dict[str, object]] = {}
    for record_date, day_threads in by_date.items():
        records = await get_meal_records(list({t.user_id for t in day_threads}), record_date)
        for record in records:
            record_lookup[(record["userId"], record["mealType"], record_date)] = record

    items = []
    for thread in threads:
        record = record_lookup.get((thread.user_id, thread.meal_type, thread.record_date))
        room = room_by_id.get(thread.room_id)
        if room is None:
            continue
        name = display_names.get(thread.user_id, f"회원{thread.user_id}")
        photo_urls = record.get("photoUrls", []) if record else []
        connected = record.get("connectedItems", []) if record else []
        image_url = photo_urls[0] if photo_urls else (connected[0].get("imageUrl") if connected else None)
        items.append({
            "id": str(thread.id),
            "roomId": str(room.id),
            "roomName": room.name,
            "roomEmoji": room.emoji,
            "memberName": name,
            "memberAvatar": room_store.avatar_text(name),
            "mealType": to_frontend_meal_type(thread.meal_type),
            "imageUrl": image_url,
            "message": (connected[0].get("name") if connected else "식사를 기록했어요"),
        })

    return items, next_cursor


async def list_weekly_ranking(
    db: AsyncSession, viewer_id: int, cursor: str | None, limit: int = 20
) -> tuple[list[dict[str, object]], str | None]:
    today = today_kst()
    week_start, week_end = week_range_kst(today)
    week_days_elapsed = (min(today, week_end) - week_start).days + 1

    result = await db.execute(select(Room).where(Room.deleted_at.is_(None), Room.ranking_opt_in.is_(True)))
    candidate_rooms = list(result.scalars().all())

    my_room_ids = {room.id for room, _m in await room_store.list_rooms_for_user(db, viewer_id)}

    entries = []
    for room in candidate_rooms:
        members = await room_store.list_active_members(db, room.id)
        days_since_start = max(0, (today - room.started_at.astimezone(_KST).date()).days)
        if len(members) < 3 or days_since_start < 7:
            continue

        user_ids = [m.user_id for m in members]
        thread_map = await _record_counts_for_range(db, room.id, user_ids, week_start, week_end)
        slot_target = len(members) * len(MEAL_TYPES_UPPER) * max(week_days_elapsed, 1)
        record_rate = round(len(thread_map) / slot_target * 100, 1) if slot_target else 0.0

        records_today = await get_meal_records(user_ids, today)
        sugars = [r["sugar"] for r in records_today if isinstance(r.get("sugar"), (int, float))]
        average_sugar = round(sum(sugars) / len(sugars), 1) if sugars else 0.0

        entries.append({
            "id": str(room.id),
            "name": room.name,
            "emoji": room.emoji,
            "memberCount": len(members),
            "recordRate": record_rate,
            "averageSugar": average_sugar,
            # 과거 주간 스냅샷이 없어 항상 0 - 모듈 docstring 참고.
            "rankMovement": 0,
            "isMine": room.id in my_room_ids,
        })

    entries.sort(key=lambda e: e["recordRate"], reverse=True)

    start_index = 0
    if cursor:
        try:
            start_index = int(cursor)
        except ValueError:
            raise room_store.RoomError(400, "INVALID_CURSOR", "cursor 형식이 올바르지 않아요.")

    page = entries[start_index:start_index + limit]
    next_cursor = str(start_index + limit) if start_index + limit < len(entries) else None
    return page, next_cursor


async def build_member_calendar(
    db: AsyncSession, room_id: uuid.UUID, member_user_id: int, year: int, month: int
) -> list[dict[str, object]]:
    """_streak_days와 같은 이유로 room_meal_threads 기준 근사치다 -
    diet-service를 매일 왕복하지 않는 대신, 얌로그 화면에서 아직 한 번도
    조회된 적 없는 날짜의 기록은 여기 안 잡힐 수 있다."""
    start = date(year, month, 1)
    end = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)

    result = await db.execute(
        select(RoomMealThread.record_date, RoomMealThread.meal_type).where(
            RoomMealThread.room_id == room_id,
            RoomMealThread.user_id == member_user_id,
            RoomMealThread.record_date >= start,
            RoomMealThread.record_date <= end,
        )
    )
    counts: dict[date, int] = {}
    for row in result.all():
        counts[row.record_date] = counts.get(row.record_date, 0) + 1

    return [{"date": d.isoformat(), "recordCount": c} for d, c in sorted(counts.items())]


_BADGE_MIN_RECIPE_COUNT = 5


async def build_room_badges(
    db: AsyncSession, room_id: uuid.UUID, members: list[RoomMember], today: date
) -> list[dict[str, object]]:
    """roomData.ts 목업의 badges 4종 중 태그 데이터 없이 계산 가능한 3종만
    구현한다(개근왕/든든이/레시피왕) - "채소한입"은 ProductRef/RecipeRef에
    카테고리 태그가 미러링돼 있지 않아 이번 범위에서 제외(후속 작업).
    room_meal_threads에 실제로 기록된 (user, date) 조합만 diet-service에
    조회해서 그 주에 diet-service를 매일 왕복하지 않는다."""
    week_start, week_end = week_range_kst(today)
    user_ids = [m.user_id for m in members]
    if not user_ids:
        return []

    thread_map = await _record_counts_for_range(db, room_id, user_ids, week_start, week_end)
    recorded_dates_by_user: dict[int, set[date]] = {}
    for (uid, d, _mt) in thread_map:
        recorded_dates_by_user.setdefault(uid, set()).add(d)

    records_by_date: dict[date, list[dict[str, object]]] = {}
    for d in {d for (_uid, d, _mt) in thread_map}:
        records_by_date[d] = await get_meal_records(user_ids, d)

    record_count_by_user: dict[int, int] = {uid: len(dates) for uid, dates in recorded_dates_by_user.items()}
    recipe_count_by_user: dict[int, int] = {}
    for day_records in records_by_date.values():
        for record in day_records:
            uid = record.get("userId")
            recipe_hits = sum(1 for item in record.get("connectedItems", []) if item.get("source") == "recipe")
            if recipe_hits:
                recipe_count_by_user[uid] = recipe_count_by_user.get(uid, 0) + recipe_hits

    display_names = await room_store.get_display_names_bulk(db, user_ids)

    def _name(uid: int) -> str:
        return display_names.get(uid, f"회원{uid}")

    badges: list[dict[str, object]] = []

    perfect_attendance = [uid for uid, dates in recorded_dates_by_user.items() if len(dates) >= 7]
    if perfect_attendance:
        badges.append({
            "emoji": "🌱",
            "name": "개근왕",
            "ownerId": str(perfect_attendance[0]),
            "ownerName": _name(perfect_attendance[0]),
            "copy": "이번 주 7일 모두 기록",
        })

    if record_count_by_user:
        top_recorder = max(record_count_by_user, key=lambda uid: record_count_by_user[uid])
        if record_count_by_user[top_recorder] > 0:
            badges.append({
                "emoji": "🍚",
                "name": "든든이",
                "ownerId": str(top_recorder),
                "ownerName": _name(top_recorder),
                "copy": "한 끼 기록을 가장 많이 남김",
            })

    eligible_recipe_users = {uid: cnt for uid, cnt in recipe_count_by_user.items() if cnt >= _BADGE_MIN_RECIPE_COUNT}
    if eligible_recipe_users:
        top_recipe_user = max(eligible_recipe_users, key=lambda uid: eligible_recipe_users[uid])
        badges.append({
            "emoji": "👩‍🍳",
            "name": "레시피왕",
            "ownerId": str(top_recipe_user),
            "ownerName": _name(top_recipe_user),
            "copy": f"레시피로 {eligible_recipe_users[top_recipe_user]}번 기록",
        })

    return badges


async def hydrate_average_sugar(db: AsyncSession, room_id: uuid.UUID, summary: dict[str, object]) -> None:
    """오늘 하루치 diet-service 조회로 평균 당류를 채운다 - room 목록 화면에서
    방마다 diet-service를 왕복하면 느려지므로, 상세 화면 등 실제로 필요한
    곳에서만 호출해서 쓴다(room_summary 계산 자체와 분리해둔 이유)."""
    members_result = await db.execute(
        select(RoomMember.user_id).where(RoomMember.room_id == room_id, RoomMember.left_at.is_(None))
    )
    user_ids = [row.user_id for row in members_result.all()]
    records = await get_meal_records(user_ids, today_kst())
    sugars = [r["sugar"] for r in records if isinstance(r.get("sugar"), (int, float))]
    summary["averageSugar"] = round(sum(sugars) / len(sugars), 1) if sugars else 0.0


async def build_meal_slots(
    db: AsyncSession, room_id: uuid.UUID, members: list[RoomMember], record_date: date, viewer_id: int
) -> list[dict[str, object]]:
    user_ids = [m.user_id for m in members]
    records = await get_meal_records(user_ids, record_date)
    records_by_key = {(r["userId"], r["mealType"]): r for r in records}
    display_names = await room_store.get_display_names_bulk(db, user_ids)

    slots: list[dict[str, object]] = []
    for member in members:
        for meal_type_db in MEAL_TYPES_UPPER:
            record_data = records_by_key.get((member.user_id, meal_type_db))
            meal_type_fe = to_frontend_meal_type(meal_type_db)

            if record_data is None:
                last_nudge = await room_store.get_last_nudge(
                    db, room_id, viewer_id, member.user_id, record_date, meal_type_db
                )
                retry_after = None
                can_send = viewer_id != member.user_id
                if last_nudge is not None:
                    elapsed = (datetime.now(timezone.utc) - last_nudge.created_at).total_seconds()
                    if elapsed < room_store.NUDGE_COOLDOWN_SECONDS:
                        retry_after = int(room_store.NUDGE_COOLDOWN_SECONDS - elapsed)
                slots.append({
                    "memberId": str(member.user_id),
                    "mealType": meal_type_fe,
                    "hasRecord": False,
                    "nutrition": None,
                    "record": None,
                    "nudge": {
                        "canSend": can_send,
                        "sentByMe": last_nudge is not None and retry_after is not None,
                        "retryAfterSeconds": retry_after,
                    },
                })
                continue

            thread = await room_store.get_or_create_thread(db, room_id, member.user_id, record_date, meal_type_db)
            connected_items = [
                {"id": item["id"], "source": item["source"], "name": item["name"], "imageUrl": item.get("imageUrl")}
                for item in record_data.get("connectedItems", [])
            ]
            comment_count = await room_store.count_comments(db, thread.id)
            reaction_count = await room_store.count_reactions(db, thread.id)
            reacted_by_me = await room_store.has_reacted(db, thread.id, viewer_id)

            title = connected_items[0]["name"] if connected_items else "식사 기록"
            member_name = display_names.get(member.user_id, f"회원{member.user_id}")
            slots.append({
                "memberId": str(member.user_id),
                "mealType": meal_type_fe,
                "hasRecord": True,
                "nutrition": {"sugar": record_data.get("sugar", 0.0), "calories": record_data.get("calories", 0.0)},
                "record": {
                    "id": str(thread.id),
                    "roomId": str(room_id),
                    "memberId": str(member.user_id),
                    "memberName": member_name,
                    "memberAvatar": room_store.avatar_text(member_name),
                    "mealType": meal_type_fe,
                    "title": title,
                    "sugar": record_data.get("sugar", 0.0),
                    "calories": record_data.get("calories", 0.0),
                    "uploadedPhotoUrls": record_data.get("photoUrls", []),
                    "connectedItems": connected_items,
                    # diet-service가 비전(사진) → 레시피 → 저당픽 순으로 이미
                    # 정렬해서 준다 - 그대로 통과시키면 프론트가 순서 걱정 없이
                    # 넘겨보기 캐러셀에 다 쓸 수 있다.
                    "orderedPhotos": record_data.get("orderedPhotos", []),
                    "recordDate": record_date.isoformat(),
                    "reactionCount": reaction_count,
                    "commentCount": comment_count,
                    "reactedByMe": reacted_by_me,
                },
                "nudge": {"canSend": False, "sentByMe": False, "retryAfterSeconds": None},
            })

    return slots
