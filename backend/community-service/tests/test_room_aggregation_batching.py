"""방 목록/랭킹 집계가 방 단위로 왕복하지 않는지 지킨다.

2026-08-10 부하테스트에서 /rooms 1건이 community→diet 내부 HTTP 19회 +
SQL 173회를 순차 실행하는 게 확인됐다(스팬 384개, 개별 작업은 0~6ms). 느린
쿼리가 아니라 호출 횟수가 병목이었다. 여기서 지키는 건 "방이 늘어도 왕복
횟수는 늘지 않는다"는 성질이다 - 값이 맞는지도 같이 본다.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.services import room_aggregation


class FakeRoom:
    def __init__(self, name: str, *, started_days_ago: int = 30, ranking_opt_in: bool = True):
        self.id = uuid.uuid4()
        self.name = name
        self.emoji = "🥗"
        self.ranking_opt_in = ranking_opt_in
        self.deleted_at = None
        self.started_at = datetime.now(timezone.utc) - timedelta(days=started_days_ago)


class FakeMember:
    def __init__(self, room_id: uuid.UUID, user_id: int, role: str = "member"):
        self.room_id = room_id
        self.user_id = user_id
        self.role = role
        self.left_at = None
        self.joined_at = datetime.now(timezone.utc)


class CallCounter:
    """get_meal_records 호출 횟수와 넘어온 user_ids·include_photos를 기록한다."""

    def __init__(self, records: list[dict[str, object]] | None = None):
        self.calls: list[list[int]] = []
        self.photo_flags: list[bool] = []
        self._records = records or []

    async def __call__(
        self, user_ids: list[int], record_date: date, *, include_photos: bool = True
    ) -> list[dict[str, object]]:
        self.calls.append(list(user_ids))
        self.photo_flags.append(include_photos)
        return [r for r in self._records if r["userId"] in set(user_ids)]


def _room_with_members(name: str, user_ids: list[int]) -> tuple[FakeRoom, list[FakeMember]]:
    room = FakeRoom(name)
    members = [FakeMember(room.id, uid, "owner" if index == 0 else "member") for index, uid in enumerate(user_ids)]
    return room, members


@pytest.fixture
def three_rooms():
    return [
        _room_with_members("한 끼", [1, 2, 3]),
        _room_with_members("밥심", [4, 5, 6]),
        _room_with_members("폭식러들", [7, 8, 9]),
    ]


async def test_room_summaries_call_diet_once_regardless_of_room_count(monkeypatch, three_rooms):
    counter = CallCounter([{"userId": uid, "sugar": 10.0, "mealType": "BREAKFAST"} for uid in range(1, 10)])
    members_by_room = {room.id: members for room, members in three_rooms}

    monkeypatch.setattr(room_aggregation, "get_meal_records", counter)
    monkeypatch.setattr(room_aggregation, "_active_members_by_room", _fake_members(members_by_room))
    monkeypatch.setattr(room_aggregation, "_record_slots_by_room", _fake_slots({}))
    monkeypatch.setattr(room_aggregation.room_store, "get_member_invite_enabled_bulk", _fake_invite_flags())

    my_rooms = [(room, members[0]) for room, members in three_rooms]
    summaries = await room_aggregation.compute_room_summaries(None, my_rooms, viewer_id=1)

    assert len(summaries) == 3
    assert len(counter.calls) == 1, f"방 3개인데 diet 호출이 {len(counter.calls)}회 — 방 단위로 왕복하고 있다"
    assert counter.calls[0] == list(range(1, 10)), "세 방의 멤버가 한 번에 묶여 나가야 한다"


async def test_room_summary_counts_only_its_own_members_as_recorded_today(monkeypatch, three_rooms):
    # 1·2번만 오늘 기록 - 첫 방(1,2,3)은 2명, 나머지 방은 0명이어야 한다.
    counter = CallCounter([{"userId": 1, "sugar": 8.0}, {"userId": 2, "sugar": 12.0}])
    members_by_room = {room.id: members for room, members in three_rooms}

    monkeypatch.setattr(room_aggregation, "get_meal_records", counter)
    monkeypatch.setattr(room_aggregation, "_active_members_by_room", _fake_members(members_by_room))
    monkeypatch.setattr(room_aggregation, "_record_slots_by_room", _fake_slots({}))
    monkeypatch.setattr(room_aggregation.room_store, "get_member_invite_enabled_bulk", _fake_invite_flags())

    my_rooms = [(room, members[0]) for room, members in three_rooms]
    summaries = await room_aggregation.compute_room_summaries(None, my_rooms, viewer_id=1)

    assert summaries[0]["recordedTodayCount"] == 2
    assert summaries[0]["averageSugar"] == 10.0
    assert [s["recordedTodayCount"] for s in summaries[1:]] == [0, 0]
    assert [s["averageSugar"] for s in summaries[1:]] == [0.0, 0.0]


async def test_weekly_ranking_calls_diet_once_for_all_candidate_rooms(monkeypatch, three_rooms):
    counter = CallCounter([{"userId": uid, "sugar": 20.0} for uid in range(1, 10)])
    members_by_room = {room.id: members for room, members in three_rooms}
    rooms = [room for room, _members in three_rooms]

    monkeypatch.setattr(room_aggregation, "get_meal_records", counter)
    monkeypatch.setattr(room_aggregation, "_active_members_by_room", _fake_members(members_by_room))
    monkeypatch.setattr(room_aggregation, "_record_slots_by_room", _fake_slots({}))
    monkeypatch.setattr(room_aggregation.room_store, "list_rooms_for_user", _fake_my_rooms([]))

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return rooms

    class FakeDB:
        async def execute(self, *_args, **_kwargs):
            return FakeResult()

    entries, cursor = await room_aggregation.list_weekly_ranking(FakeDB(), viewer_id=1, cursor=None)

    assert len(entries) == 3
    assert cursor is None
    assert len(counter.calls) == 1, f"후보 방 3개인데 diet 호출이 {len(counter.calls)}회"
    assert counter.calls[0] == list(range(1, 10))


async def test_weekly_ranking_skips_ineligible_rooms_before_calling_diet(monkeypatch):
    """3명 미만/시작 7일 미만 방은 diet 조회 대상에서 빠져야 한다."""
    young = FakeRoom("갓 만든 방", started_days_ago=2)
    small = FakeRoom("2명 방")
    mature, mature_members = _room_with_members("자격 있는 방", [10, 11, 12])

    members_by_room = {
        young.id: [FakeMember(young.id, uid) for uid in (1, 2, 3)],
        small.id: [FakeMember(small.id, uid) for uid in (4, 5)],
        mature.id: mature_members,
    }
    counter = CallCounter([])
    rooms = [young, small, mature]

    monkeypatch.setattr(room_aggregation, "get_meal_records", counter)
    monkeypatch.setattr(room_aggregation, "_active_members_by_room", _fake_members(members_by_room))
    monkeypatch.setattr(room_aggregation, "_record_slots_by_room", _fake_slots({}))
    monkeypatch.setattr(room_aggregation.room_store, "list_rooms_for_user", _fake_my_rooms([]))

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return rooms

    class FakeDB:
        async def execute(self, *_args, **_kwargs):
            return FakeResult()

    entries, _cursor = await room_aggregation.list_weekly_ranking(FakeDB(), viewer_id=1, cursor=None)

    assert [e["name"] for e in entries] == ["자격 있는 방"]
    assert counter.calls == [[10, 11, 12]], "자격 미달 방의 멤버까지 diet에 물어보고 있다"


async def test_summary_uses_this_rooms_own_week_slots(monkeypatch, three_rooms):
    """주간 기록률/내 참여일은 배치로 읽어온 방별 슬롯에서 계산돼야 한다."""
    (first_room, first_members), *_rest = three_rooms
    monday, _sunday = room_aggregation.week_range_kst(room_aggregation.today_kst())
    slots = {
        first_room.id: {
            (1, monday, "BREAKFAST"),
            (1, monday, "LUNCH"),
            (1, monday + timedelta(days=1), "DINNER"),
            (2, monday, "SNACK"),
        }
    }

    monkeypatch.setattr(room_aggregation, "get_meal_records", CallCounter([]))
    monkeypatch.setattr(
        room_aggregation, "_active_members_by_room", _fake_members({room.id: members for room, members in three_rooms})
    )
    monkeypatch.setattr(room_aggregation, "_record_slots_by_room", _fake_slots(slots))
    monkeypatch.setattr(room_aggregation.room_store, "get_member_invite_enabled_bulk", _fake_invite_flags())

    my_rooms = [(room, members[0]) for room, members in three_rooms]
    summaries = await room_aggregation.compute_room_summaries(None, my_rooms, viewer_id=1)

    # 1번(뷰어)이 기록한 날짜는 월·화 이틀 - 슬롯 3개지만 날짜 기준으로는 2일.
    assert summaries[0]["myParticipationDays"] == 2
    assert summaries[0]["monthlyRecordRate"] > 0
    # 다른 방은 이 방의 슬롯을 물려받지 않는다.
    assert summaries[1]["myParticipationDays"] == 0
    assert summaries[1]["monthlyRecordRate"] == 0.0


async def test_home_summaries_do_not_ask_diet_to_sign_photos(monkeypatch, three_rooms):
    """홈 방 요약은 "오늘 기록한 사람 집합"과 사람별 당류만 쓴다 - 사진 서명
    URL은 한 장도 안 쓰면서 받아왔다. 왕복을 한 번으로 줄인 뒤로는 그 한 번에
    모든 방의 멤버가 몰리므로, 사진을 켜두면 오히려 한 응답에 실리는 사진 수가
    방 수만큼 늘어난다 - 배치와 이 플래그를 같이 가야 하는 이유."""
    counter = CallCounter([{"userId": uid, "sugar": 10.0} for uid in range(1, 10)])
    members_by_room = {room.id: members for room, members in three_rooms}

    monkeypatch.setattr(room_aggregation, "_INCLUDE_PHOTOS_WHERE_UNUSED", False)
    monkeypatch.setattr(room_aggregation, "get_meal_records", counter)
    monkeypatch.setattr(room_aggregation, "_active_members_by_room", _fake_members(members_by_room))
    monkeypatch.setattr(room_aggregation, "_record_slots_by_room", _fake_slots({}))
    monkeypatch.setattr(room_aggregation.room_store, "get_member_invite_enabled_bulk", _fake_invite_flags())

    my_rooms = [(room, members[0]) for room, members in three_rooms]
    await room_aggregation.compute_room_summaries(None, my_rooms, viewer_id=1)

    assert counter.photo_flags == [False], "홈 요약이 안 쓰는 사진 서명을 여전히 요청하고 있다"


async def test_photo_skipping_can_be_switched_back_off(monkeypatch, three_rooms):
    """ROOMS_SKIP_UNUSED_PHOTOS를 끄면 예전처럼 전부 사진을 받아온다 -
    모니터링팀이 부하테스트에서 이 값만 뒤집어 A/B를 재기로 했으므로, 되돌리는
    쪽도 실제로 동작해야 한다."""
    counter = CallCounter([])
    members_by_room = {room.id: members for room, members in three_rooms}

    monkeypatch.setattr(room_aggregation, "_INCLUDE_PHOTOS_WHERE_UNUSED", True)
    monkeypatch.setattr(room_aggregation, "get_meal_records", counter)
    monkeypatch.setattr(room_aggregation, "_active_members_by_room", _fake_members(members_by_room))
    monkeypatch.setattr(room_aggregation, "_record_slots_by_room", _fake_slots({}))
    monkeypatch.setattr(room_aggregation.room_store, "get_member_invite_enabled_bulk", _fake_invite_flags())

    my_rooms = [(room, members[0]) for room, members in three_rooms]
    await room_aggregation.compute_room_summaries(None, my_rooms, viewer_id=1)

    assert counter.photo_flags == [True]


def test_average_sugar_ignores_non_numeric_and_other_rooms():
    sugar_by_user = room_aggregation._sugars_by_user([
        {"userId": 1, "sugar": 10.0},
        {"userId": 1, "sugar": 20.0},
        {"userId": 2, "sugar": "많이"},  # 숫자가 아니면 무시
        {"userId": 3, "sugar": 90.0},  # 다른 방 멤버
    ])

    assert room_aggregation._average_sugar([1, 2], sugar_by_user) == 15.0
    assert room_aggregation._average_sugar([2], sugar_by_user) == 0.0


def _fake_members(members_by_room):
    async def _call(_db, room_ids):
        return {room_id: members_by_room.get(room_id, []) for room_id in room_ids}

    return _call


def _fake_slots(slots_by_room):
    async def _call(_db, members_by_room, _start, _end):
        return {room_id: slots_by_room.get(room_id, set()) for room_id in members_by_room}

    return _call


def _fake_invite_flags():
    async def _call(_db, room_ids):
        return {room_id: False for room_id in room_ids}

    return _call


def _fake_my_rooms(rows):
    async def _call(_db, _user_id):
        return rows

    return _call
