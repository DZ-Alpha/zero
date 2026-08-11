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

from app.core.config import settings
from app.models.room import Room
from app.models.room_member import RoomMember
from app.models.room_meal_thread import RoomMealThread
from app.services import room_store
from app.services.diet_client import get_meal_records

_KST = ZoneInfo("Asia/Seoul")

# 이 모듈은 diet-service를 6곳에서 부르는데, 그중 사진을 실제로 화면에 쓰는 건
# list_recent_activities(카드 대표 사진 1장)와 build_meal_slots(넘겨보기 캐러셀)
# 두 곳뿐이다. 나머지 4곳(방 요약/멤버 목록/주간 랭킹/배지)은 sugar나
# connectedItems만 읽으면서도 "사람 수 x 사진 수"만큼의 SigV4 서명 URL을 받아
# 그대로 버리고 있었다 - 특히 주간 랭킹은 한 번에 77명을 넘기면서 sugar만 쓴다.
# 설정을 끄면 이 값이 True가 되어 예전 동작(전부 사진 포함)으로 되돌아간다.
_INCLUDE_PHOTOS_WHERE_UNUSED = not settings.rooms_skip_unused_photos
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

    # room_meal_thread는 누군가 방 화면을 열어야만 생기는 근사치라(위 주석 참고),
    # 아직 아무도 방을 안 열어본 오늘 기록은 여기 안 잡힌다 - 홈 화면은 방
    # 상세를 열지 않고도 "오늘 몇 명 기록했는지"를 보여줘야 하므로, 오늘 하루는
    # diet-service 원본을 직접 조회해 정확한 값을 쓴다(주간 기록률은 기존처럼
    # thread 근사치를 유지 - 매번 diet-service를 왕복하면 느려짐).
    # 여기서 records_today로 하는 일은 "오늘 기록한 사람 수 세기"와 아래
    # 평균 당류 계산뿐이라 사진은 필요 없다.
    records_today = await get_meal_records(user_ids, today, include_photos=_INCLUDE_PHOTOS_WHERE_UNUSED)
    recorded_today = len({r["userId"] for r in records_today})
    week_record_count = len(thread_map)
    my_participation_days = len({d for (uid, d, _mt) in thread_map if uid == viewer_id})

    # hydrate_average_sugar가 따로 있던 이유는 "room 목록 화면에서 방마다
    # diet-service를 왕복하면 느려진다"였는데(과거 주석), 정작 모든 호출부가
    # compute_room_summary 바로 뒤에서 hydrate_average_sugar를 불러 같은
    # user_ids/오늘 날짜로 get_meal_records를 한 번 더(중복) 왕복하고 있었다
    # (2026-07-26 실사용 중 "얌로그 진입 시 버퍼링" 재현 - 방마다 diet-service
    # 왕복이 2번씩이었음). 위에서 이미 받아온 records_today를 그대로 써서
    # 왕복 횟수를 절반으로 줄인다.
    sugars_today = [r["sugar"] for r in records_today if isinstance(r.get("sugar"), (int, float))]
    average_sugar = round(sum(sugars_today) / len(sugars_today), 1) if sugars_today else 0.0

    eligible = member_count >= 3 and days_since_start >= 7 and room.ranking_opt_in
    member_invite_enabled = await room_store.get_member_invite_enabled(db, room.id)

    return {
        "id": str(room.id),
        "name": room.name,
        "emoji": room.emoji,
        "role": membership.role,
        "memberCount": member_count,
        "recordedTodayCount": recorded_today,
        "daysSinceStart": days_since_start,
        # 이번 주 기록 개수 대비 기록률(§8 권장 분모 - slot_target=0 방지).
        "averageSugar": average_sugar,
        "monthlyRecordRate": round(week_record_count / slot_target * 100, 1) if slot_target else 0.0,
        "myParticipationDays": my_participation_days,
        "rankingOptIn": room.ranking_opt_in,
        "rank": None,
        "rankingEligibility": {
            "eligible": eligible,
            "missingMemberCount": max(0, 3 - member_count),
            "remainingDays": max(0, 7 - days_since_start),
        },
        "permissions": room_store.compute_permissions(room, membership, member_count, member_invite_enabled),
    }


_MEMBER_COLORS = ["#F4A261", "#2A9D8F", "#E76F51", "#457B9D", "#8D5A97", "#A3B18A"]


def _color_for(user_id: int) -> str:
    return _MEMBER_COLORS[user_id % len(_MEMBER_COLORS)]


async def _streak_days_bulk(db: AsyncSession, room_id: uuid.UUID, user_ids: list[int], today: date) -> dict[int, int]:
    """오늘부터 거슬러 올라가며 이 방에서 기록이 있었던 연속 일수 - 멤버별로.

    room_meal_threads는 그 (user, date, mealType) 조합이 방 화면에서 한 번이라도
    조회돼 get_or_create_thread를 거쳤을 때만 생긴다 - 즉 이 스트릭은 "얌로그
    화면에서 확인된 기록" 기준의 근사치다. 정확한 스트릭이 필요해지면
    diet-service 원본을 기간 조회해야 한다(§8 재집계 정책 확정 후 개선 대상).

    예전엔 멤버마다 이 쿼리를 따로 불러(N+1) 방 상세를 열 때마다 멤버 수만큼
    왕복이 났다(2026-08-01 부하테스트 - community-svc 새 최대 병목 원인 중
    하나) - 방 전체를 한 번에 읽어 유저별로 묶은 뒤 스트릭은 파이썬에서 계산한다.
    """
    if not user_ids:
        return {}
    result = await db.execute(
        select(RoomMealThread.user_id, RoomMealThread.record_date)
        .where(RoomMealThread.room_id == room_id, RoomMealThread.user_id.in_(user_ids))
        .distinct()
    )
    recorded_days_by_user: dict[int, set[date]] = {}
    for row in result.all():
        recorded_days_by_user.setdefault(row.user_id, set()).add(row.record_date)

    streaks: dict[int, int] = {}
    for uid in user_ids:
        recorded_days = recorded_days_by_user.get(uid, set())
        streak = 0
        cursor = today
        while cursor in recorded_days:
            streak += 1
            cursor -= timedelta(days=1)
        streaks[uid] = streak
    return streaks


async def build_room_members(db: AsyncSession, room: Room, members: list[RoomMember], viewer_id: int) -> list[dict[str, object]]:
    user_ids = [m.user_id for m in members]
    display_names = await room_store.get_display_names_bulk(db, user_ids)
    today = today_kst()
    week_start, week_end = week_range_kst(today)
    week_days_elapsed = (min(today, week_end) - week_start).days + 1
    thread_map = await _record_counts_for_range(db, room.id, user_ids, week_start, week_end)

    # 멤버 목록은 사람별 오늘 당류 합계만 쓴다 - 사진은 방 상세의 끼니 슬롯에서 따로 받는다.
    records_today = await get_meal_records(user_ids, today, include_photos=_INCLUDE_PHOTOS_WHERE_UNUSED)
    sugar_today_by_user: dict[int, float] = {}
    for record in records_today:
        uid = record["userId"]
        sugar_today_by_user[uid] = sugar_today_by_user.get(uid, 0.0) + float(record.get("sugar", 0.0))
    streaks = await _streak_days_bulk(db, room.id, user_ids, today)

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
            "streakDays": streaks.get(member.user_id, 0),
            "color": _color_for(member.user_id),
        })
    return result


async def list_recent_activities(
    db: AsyncSession, viewer_id: int, cursor: str | None, limit: int = 20, today_only: bool = False,
    include_self: bool = False,
) -> tuple[list[dict[str, object]], str | None]:
    """today_only=True면 오늘(KST) 기록만 반환한다 - 홈 화면(/rooms)의 "방금
    올라왔어요"/방 카드 사진 미리보기가 여러 방을 합쳐 최근 20건만 보다 보니,
    당장은 조용한 방의 카드에 며칠 지난 사진이 "오늘 기록 보러가기" 버튼과 함께
    뜨는 문제가 있었다(2026-07-30 리포트). "더보기"(GET /rooms/activities) 같은
    과거 이력 탐색은 이 필터 없이 그대로 전체 히스토리를 페이지네이션한다.

    include_self=False(기본)면 내 기록은 뺀다 - "모임의 새 식탁"처럼 "다른
    멤버들이 뭘 먹었나"를 보는 피드용. 방 카드 사진 미리보기/오늘 기록 요약처럼
    "오늘 이 방에 (나를 포함해) 실제로 무슨 기록이 있었나"가 필요한 곳은
    include_self=True로 불러야 한다 - 아니면 오늘 나 혼자만 기록한 방은
    recordedTodayCount>0인데도 사진이 하나도 안 보이는 것처럼 보인다
    (2026-07-31 리포트)."""
    my_rooms = await room_store.list_rooms_for_user(db, viewer_id)
    room_by_id = {room.id: room for room, _membership in my_rooms}
    if not room_by_id:
        return [], None

    conditions = [RoomMealThread.room_id.in_(room_by_id.keys())]
    if not include_self:
        # 내 기록은 홈 "모임의 새 식탁"에 안 띄운다(2026-07-30 요청) - 이 피드는
        # "다른 멤버들이 뭘 먹었나"를 보는 곳이고, 내가 방금 올린 사진이 항상
        # 맨 앞을 차지하면 정작 남의 새 기록이 밀려난다.
        conditions.append(RoomMealThread.user_id != viewer_id)
    stmt = select(RoomMealThread).where(*conditions)
    if today_only:
        stmt = stmt.where(RoomMealThread.record_date == today_kst())
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
        connected = record.get("connectedItems", []) if record else []
        ordered_photos = record.get("orderedPhotos", []) if record else []
        # build_meal_slots와 같은 우선순위(비전 → 레시피 → 저당픽)로 대표 사진
        # 하나를 고른다 - 이 피드는 카드 하나당 사진 한 장만 보여주므로 전체
        # orderedPhotos를 다 넘길 필요는 없다.
        image_url = ordered_photos[0]["imageUrl"] if ordered_photos else None
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


async def build_incoming_nudges(
    db: AsyncSession, viewer_id: int, room_by_id: dict[uuid.UUID, Room], room_id: uuid.UUID | None = None
) -> list[dict[str, object]]:
    """방/홈 화면 진입 시 보여줄 "누가 나를 콕 찔렀는지" 목록을 만들고, 한 번
    보여준 뒤 바로 acknowledge 처리한다(같은 화면을 다시 열어도 반복 노출 안 됨).
    room_id를 주면 그 방으로 한정(방 상세), 안 주면 뷰어의 모든 방(홈)."""
    nudges = await room_store.list_incoming_nudges(db, viewer_id, room_id)
    if not nudges:
        return []

    display_names = await room_store.get_display_names_bulk(db, [n.sender_id for n in nudges])
    items: list[dict[str, object]] = []
    acknowledged_ids: list[uuid.UUID] = []
    for nudge in nudges:
        room = room_by_id.get(nudge.room_id)
        acknowledged_ids.append(nudge.id)
        if room is None:
            continue
        sender_name = display_names.get(nudge.sender_id, f"회원{nudge.sender_id}")
        items.append({
            "id": str(nudge.id),
            "roomId": str(room.id),
            "roomName": room.name,
            "senderName": sender_name,
            "mealType": to_frontend_meal_type(nudge.meal_type),
        })

    await room_store.acknowledge_nudges(db, acknowledged_ids)
    return items


async def _active_members_by_room(
    db: AsyncSession, room_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[RoomMember]]:
    """여러 방의 활성 멤버를 한 번에 읽는다 - 정렬 기준은 list_active_members와 동일."""
    if not room_ids:
        return {}
    result = await db.execute(
        select(RoomMember)
        .where(RoomMember.room_id.in_(room_ids), RoomMember.left_at.is_(None))
        .order_by((RoomMember.role != "owner"), RoomMember.joined_at, RoomMember.user_id)
    )
    grouped: dict[uuid.UUID, list[RoomMember]] = {room_id: [] for room_id in room_ids}
    for member in result.scalars().all():
        grouped[member.room_id].append(member)
    return grouped


async def _record_counts_by_room(
    db: AsyncSession, members_by_room: dict[uuid.UUID, list[RoomMember]], start: date, end: date
) -> dict[uuid.UUID, int]:
    """방별 주간 기록 슬롯 수를 한 번에 센다 - _record_counts_for_range의 배치판.

    _record_counts_for_range가 user_ids로 걸러내던 것과 같게, 지금 활성 멤버가
    아닌 사용자(탈퇴자)의 과거 기록은 세지 않는다."""
    room_ids = list(members_by_room)
    if not room_ids:
        return {}
    result = await db.execute(
        select(RoomMealThread.room_id, RoomMealThread.user_id,
               RoomMealThread.record_date, RoomMealThread.meal_type).where(
            RoomMealThread.room_id.in_(room_ids),
            RoomMealThread.record_date >= start,
            RoomMealThread.record_date <= end,
        )
    )
    active_ids = {room_id: {m.user_id for m in members} for room_id, members in members_by_room.items()}
    counts: dict[uuid.UUID, set[tuple[int, date, str]]] = {room_id: set() for room_id in room_ids}
    for row in result.all():
        if row.user_id in active_ids[row.room_id]:
            counts[row.room_id].add((row.user_id, row.record_date, row.meal_type))
    return {room_id: len(slots) for room_id, slots in counts.items()}


async def list_weekly_ranking(
    db: AsyncSession, viewer_id: int, cursor: str | None, limit: int = 20
) -> tuple[list[dict[str, object]], str | None]:
    today = today_kst()
    week_start, week_end = week_range_kst(today)
    week_days_elapsed = (min(today, week_end) - week_start).days + 1

    result = await db.execute(select(Room).where(Room.deleted_at.is_(None), Room.ranking_opt_in.is_(True)))
    candidate_rooms = list(result.scalars().all())

    my_room_ids = {room.id for room, _m in await room_store.list_rooms_for_user(db, viewer_id)}

    # 예전에는 방 하나마다 (멤버 조회 + 스레드 집계 + diet-service 왕복)을 순차로
    # 돌았다. 랭킹 대상 방이 늘수록 요청 시간이 그대로 비례해서 늘었고, 특히
    # diet-service 왕복(방당 200~700ms)이 지배적이었다 - 실측(2026-08-11)에서
    # 자격 방 15개일 때 /rooms 가 p50 2.5s, p95 8.5s 였고 로그상 한 요청이
    # diet-service 를 12회 이상 순차 호출했다. 방 수와 무관하게 왕복 1회로
    # 고정되도록 아래 3단계로 나눈다.
    members_by_room = await _active_members_by_room(db, [room.id for room in candidate_rooms])

    qualified: list[tuple[Room, list[RoomMember]]] = []
    for room in candidate_rooms:
        members = members_by_room.get(room.id, [])
        days_since_start = max(0, (today - room.started_at.astimezone(_KST).date()).days)
        if len(members) < 3 or days_since_start < 7:
            continue
        qualified.append((room, members))

    recorded_slots = await _record_counts_by_room(
        db, {room.id: members for room, members in qualified}, week_start, week_end
    )

    # 자격 방 전체의 멤버를 합쳐 한 번만 조회한다. 한 사용자가 여러 방에 속해도
    # 오늘 기록은 같으므로 중복 호출할 이유가 없다.
    all_user_ids = sorted({m.user_id for _, members in qualified for m in members})
    sugars_by_user: dict[int, list[float]] = {}
    # 랭킹은 sugar 하나만 쓰는데 한 번에 넘기는 인원이 가장 많다(부하테스트
    # 픽스처 기준 77명) - 사진을 끄는 효과가 가장 큰 호출부다.
    for record in await get_meal_records(all_user_ids, today, include_photos=_INCLUDE_PHOTOS_WHERE_UNUSED):
        sugar = record.get("sugar")
        if isinstance(sugar, (int, float)):
            sugars_by_user.setdefault(record["userId"], []).append(float(sugar))

    entries = []
    for room, members in qualified:
        slot_target = len(members) * len(MEAL_TYPES_UPPER) * max(week_days_elapsed, 1)
        record_rate = round(recorded_slots.get(room.id, 0) / slot_target * 100, 1) if slot_target else 0.0

        sugars = [s for m in members for s in sugars_by_user.get(m.user_id, [])]
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


async def build_room_calendar(
    db: AsyncSession, room_id: uuid.UUID, viewer_id: int, year: int, month: int
) -> list[dict[str, object]]:
    """방 상세 캘린더(2026-07-30 연장업무 - 과거 날짜 조회 진입점)용 월간
    집계. 날짜별로 방 전체 기록 수와 그중 내 기록 수를 나눠 주면, 프론트가
    "남만 올린 날"과 "나도 올린 날"을 색으로 구분한다. build_member_calendar와
    같은 room_meal_threads 근사치 기준이다."""
    start = date(year, month, 1)
    end = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)

    result = await db.execute(
        select(RoomMealThread.record_date, RoomMealThread.user_id).where(
            RoomMealThread.room_id == room_id,
            RoomMealThread.record_date >= start,
            RoomMealThread.record_date <= end,
        )
    )
    total: dict[date, int] = {}
    mine: dict[date, int] = {}
    for row in result.all():
        total[row.record_date] = total.get(row.record_date, 0) + 1
        if row.user_id == viewer_id:
            mine[row.record_date] = mine.get(row.record_date, 0) + 1

    return [
        {"date": d.isoformat(), "recordCount": c, "myRecordCount": mine.get(d, 0)}
        for d, c in sorted(total.items())
    ]


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
        # 배지는 connectedItems의 source="recipe" 개수만 센다 - connectedItems는
        # includePhotos와 무관하게 항상 내려오므로(서명 대상이 아님) 끌 수 있다.
        records_by_date[d] = await get_meal_records(user_ids, d, include_photos=_INCLUDE_PHOTOS_WHERE_UNUSED)

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


async def build_meal_slots(
    db: AsyncSession, room_id: uuid.UUID, members: list[RoomMember], record_date: date, viewer_id: int
) -> list[dict[str, object]]:
    # 예전엔 (멤버 × mealType) 슬롯마다 get_or_create_thread/count_comments/
    # count_reactions/has_reacted/get_last_nudge를 각각 따로 불러 방 상세를
    # 열 때마다 최대 멤버수×4×5번의 DB 왕복이 났다(2026-08-01 부하테스트에서
    # diet-svc 이벤트 루프 고정 이후 community-svc가 새 최대 병목으로 드러난
    # 가장 큰 원인). 슬롯을 "기록 있음/없음"으로 먼저 나눈 뒤 각각 한 번씩만
    # 벌크로 조회·생성하고, 실제 슬롯 조립은 미리 받아온 dict 조회만으로 한다.
    user_ids = [m.user_id for m in members]
    records = await get_meal_records(user_ids, record_date)
    records_by_key = {(r["userId"], r["mealType"]): r for r in records}
    display_names = await room_store.get_display_names_bulk(db, user_ids)

    has_record_keys: list[tuple[int, str]] = []
    no_record_keys: list[tuple[int, str]] = []
    for member in members:
        for meal_type_db in MEAL_TYPES_UPPER:
            key = (member.user_id, meal_type_db)
            (has_record_keys if key in records_by_key else no_record_keys).append(key)

    threads = await room_store.get_or_create_threads_bulk(db, room_id, record_date, has_record_keys)
    thread_ids = [t.id for t in threads.values()]
    comment_counts = await room_store.count_comments_bulk(db, thread_ids)
    reaction_counts = await room_store.count_reactions_bulk(db, thread_ids)
    reacted_thread_ids = await room_store.reacted_thread_ids_bulk(db, thread_ids, viewer_id)

    no_record_target_ids = {uid for uid, _mt in no_record_keys}
    no_record_meal_types = {mt for _uid, mt in no_record_keys}
    last_nudges = await room_store.get_last_nudges_bulk(
        db, room_id, viewer_id, no_record_target_ids, record_date, no_record_meal_types
    )

    slots: list[dict[str, object]] = []
    for member in members:
        for meal_type_db in MEAL_TYPES_UPPER:
            record_data = records_by_key.get((member.user_id, meal_type_db))
            meal_type_fe = to_frontend_meal_type(meal_type_db)

            if record_data is None:
                last_nudge = last_nudges.get((member.user_id, meal_type_db))
                retry_after = None
                # 본인 카드엔 버튼 자체가 없고(canSend/refused 모두 False),
                # 콕 찌르기를 거부한 멤버(nudge_notifications off)는 버튼을
                # 비활성으로 보여준다(refused=True - 숨기지 말라는 2026-07-30
                # 요청). 발송 시점엔 send_nudge가 한 번 더 검사한다(NUDGE_REFUSED).
                is_other = viewer_id != member.user_id
                can_send = is_other and member.nudge_notifications
                refused = is_other and not member.nudge_notifications
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
                        "refused": refused,
                        "sentByMe": last_nudge is not None and retry_after is not None,
                        "retryAfterSeconds": retry_after,
                    },
                })
                continue

            thread = threads[(member.user_id, meal_type_db)]
            connected_items = [
                {"id": item["id"], "source": item["source"], "name": item["name"], "imageUrl": item.get("imageUrl")}
                for item in record_data.get("connectedItems", [])
            ]
            comment_count = comment_counts.get(thread.id, 0)
            reaction_count = reaction_counts.get(thread.id, 0)
            reacted_by_me = thread.id in reacted_thread_ids

            ordered_photos = record_data.get("orderedPhotos", [])
            # 기본 표시 이름 - 처음 보이는 사진(비전 → 레시피 → 저당픽 순 첫 장)
            # 이름을 우선 쓴다. 넘겨보기로 사진을 바꾸면 프론트가 orderedPhotos의
            # 각 항목 name으로 갈아끼운다(2026-07-26 - 예전엔 connected_items[0]
            # 이름 하나로 고정돼서, 비전으로만 기록한 식사는 이름이 아예 안
            # 뜨고 사진을 넘겨도 이름이 안 바뀌었다).
            title = ordered_photos[0]["name"] if ordered_photos else (connected_items[0]["name"] if connected_items else "식사 기록")
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
                    "orderedPhotos": ordered_photos,
                    "recordDate": record_date.isoformat(),
                    "reactionCount": reaction_count,
                    "commentCount": comment_count,
                    "reactedByMe": reacted_by_me,
                },
                "nudge": {"canSend": False, "refused": False, "sentByMe": False, "retryAfterSeconds": None},
            })

    return slots
