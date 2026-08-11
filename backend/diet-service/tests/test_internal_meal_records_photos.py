import uuid
from unittest import IsolatedAsyncioTestCase, mock

from app.routers.diet import _resolve_photo_entries


class ResolvePhotoEntriesTests(IsolatedAsyncioTestCase):
    """GET /diet/internal/meal-records의 includePhotos 파라미터.

    얌로그가 이 엔드포인트를 부르는 6곳 중 4곳은 사진을 한 장도 안 쓰면서
    "사람 수 x 사진 수"만큼 SigV4 서명 URL을 받아 그대로 버렸다. 이 파라미터의
    핵심 계약은 "false면 서명을 안 한다"이지 "false면 결과에서 뺀다"가 아니다 -
    응답에서만 빼고 서명은 그대로 하면 비용이 하나도 안 줄기 때문에, 아래
    테스트는 presign이 호출되지 않는 것 자체를 검증한다."""

    def setUp(self) -> None:
        self.log_a = uuid.uuid4()
        self.log_b = uuid.uuid4()
        self.object_keys = {
            self.log_a: "diet-photos/7/a.jpg",
            self.log_b: "diet-photos/7/b.jpg",
        }
        self.item_names = {self.log_a: ["김치찌개", "공기밥"]}

    async def test_skips_signing_entirely_when_photos_not_requested(self) -> None:
        with mock.patch("app.routers.diet.presign_diet_photo_url") as presign:
            entries = await _resolve_photo_entries(self.object_keys, self.item_names, include_photos=False)

        self.assertEqual(entries, [])
        presign.assert_not_called()

    async def test_signs_every_photo_when_requested(self) -> None:
        with mock.patch("app.routers.diet.presign_diet_photo_url", side_effect=lambda key: f"/b/{key}?sig=x") as presign:
            entries = await _resolve_photo_entries(self.object_keys, self.item_names, include_photos=True)

        self.assertEqual(presign.call_count, 2)
        self.assertEqual([entry["imageUrl"] for entry in entries], ["/b/diet-photos/7/a.jpg?sig=x", "/b/diet-photos/7/b.jpg?sig=x"])

    async def test_names_each_photo_with_its_own_recognized_items(self) -> None:
        # 사진마다 그 사진에서 인식된 이름을 실어 보낸다 - 이름이 없는 사진은
        # 기본 문구로 채운다(넘겨보기 캐러셀에서 이름이 빈칸으로 뜨지 않게).
        with mock.patch("app.routers.diet.presign_diet_photo_url", side_effect=lambda key: f"/b/{key}"):
            entries = await _resolve_photo_entries(self.object_keys, self.item_names, include_photos=True)

        self.assertEqual([entry["name"] for entry in entries], ["김치찌개, 공기밥", "사진으로 기록한 식사"])

    async def test_no_photos_to_sign_is_not_an_error(self) -> None:
        with mock.patch("app.routers.diet.presign_diet_photo_url") as presign:
            entries = await _resolve_photo_entries({}, {}, include_photos=True)

        self.assertEqual(entries, [])
        presign.assert_not_called()
