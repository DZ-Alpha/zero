"""스왑 소스 확보 경로 - product_id 우선, 이름 검색 폴백.

2026-08-12 SwapCard 미노출 회고 §3. vision 아이템의 94.7%가 이미
meal_item.product_id를 갖고 있는데도 인식된 이름으로 /search를 다시 뒤지고
있었다. product_id 경로를 추가하면서, 두 응답의 키가 다르다는 점(dang↔sugar,
cal↔calories)이 새 함정이 됐다 - 매핑을 빠뜨리면 sugar가 None으로 읽혀
is_already_low_sugar가 모든 소스를 조용히 걸러낸다.
"""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase

from app.routers.diet import _source_from_product_detail, _swap_sources_for_item
from app.services.swap_rules import is_already_low_sugar, is_credible_product_match

PRODUCT_DETAIL = {
    "name": "고고단 다이어트 단백질쉐이크 모카초코프라페맛",
    "brand": "고고단",
    "category": "음료",
    "foodType": "단백질음료",
    "serving": "100g",
    "cal": 120.0,
    "dang": 13.4,
    "allerg": ["우유"],
    "imageUrl": "https://example.test/a.png",
}


class FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class FakeClient:
    """호출된 URL을 기록해서 /search를 탔는지 /product를 탔는지 구분한다."""

    def __init__(self, detail=None, search_items=None):
        self.calls: list[str] = []
        self._detail = detail if detail is not None else PRODUCT_DETAIL
        self._search_items = search_items or []

    async def get(self, url: str, params=None):
        self.calls.append(url)
        if url.endswith("/product"):
            return FakeResponse(self._detail)
        return FakeResponse({"items": self._search_items})


class SourceMappingTests(TestCase):
    def test_detail_keys_are_mapped_to_search_shape(self) -> None:
        source = _source_from_product_detail("pid-1", PRODUCT_DETAIL)

        self.assertEqual(source["id"], "pid-1")  # 상세 응답에는 id가 없다
        self.assertEqual(source["sugar"], 13.4)  # dang → sugar
        self.assertEqual(source["calories"], 120.0)  # cal → calories
        self.assertEqual(source["serving"], "100g")
        self.assertEqual(source["foodType"], "단백질음료")

    def test_mapped_source_is_not_treated_as_already_low_sugar(self) -> None:
        """매핑이 빠지면 sugar가 None → float(None or 0) <= 0 → 전 상품 탈락."""
        source = _source_from_product_detail("pid-1", PRODUCT_DETAIL)

        self.assertFalse(is_already_low_sugar(source))

    def test_allergen_tags_do_not_leak_into_low_sugar_labels(self) -> None:
        detail = {**PRODUCT_DETAIL, "allerg": ["우유"], "name": "일반 초코쉐이크"}
        source = _source_from_product_detail("pid-1", detail)

        self.assertEqual(source["tags"], [])
        self.assertFalse(is_already_low_sugar(source))

    def test_name_marker_still_filters_low_sugar_products(self) -> None:
        detail = {**PRODUCT_DETAIL, "name": "저당 초코쉐이크"}
        source = _source_from_product_detail("pid-1", detail)

        self.assertTrue(is_already_low_sugar(source))


class SwapSourceResolutionTests(IsolatedAsyncioTestCase):
    async def test_product_id_skips_the_name_search(self) -> None:
        client = FakeClient()
        item = SimpleNamespace(product_id="pid-1", item_name="단백질쉐이크")

        sources = await _swap_sources_for_item(client, "http://svc", item, "단백질쉐이크", lambda _r: None)

        self.assertEqual([c for c in client.calls if c.endswith("/search")], [])
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["sugar"], 13.4)

    async def test_falls_back_to_search_without_product_id(self) -> None:
        client = FakeClient(search_items=[{"name": "종가집 김치찌개 500g", "sugar": 4.0}])
        item = SimpleNamespace(product_id=None, item_name="김치찌개")

        sources = await _swap_sources_for_item(client, "http://svc", item, "김치찌개", lambda _r: None)

        self.assertTrue(any(c.endswith("/search") for c in client.calls))
        self.assertEqual([s["name"] for s in sources], ["종가집 김치찌개 500g"])

    async def test_records_drop_reason_when_search_finds_nothing(self) -> None:
        client = FakeClient(search_items=[])
        item = SimpleNamespace(product_id=None, item_name="없는음식")
        reasons: list[str] = []

        sources = await _swap_sources_for_item(client, "http://svc", item, "없는음식", reasons.append)

        self.assertEqual(sources, [])
        self.assertEqual(reasons, ["search_empty"])

    async def test_records_drop_reason_when_name_match_fails(self) -> None:
        client = FakeClient(search_items=[{"name": "코카콜라 500ml"}])
        item = SimpleNamespace(product_id=None, item_name="탄산음료")
        reasons: list[str] = []

        sources = await _swap_sources_for_item(client, "http://svc", item, "탄산음료", reasons.append)

        self.assertEqual(sources, [])
        self.assertEqual(reasons, ["name_match_failed"])


class CredibleMatchTests(TestCase):
    """폴백 경로로 남는 이름 게이트 - 지금까지 테스트가 0건이었다.
    마지막 두 건은 이 게이트의 알려진 한계다(양쪽에 서로 다른 수식어)."""

    def test_known_behaviour(self) -> None:
        cases = [
            ("김치찌개", "종가집 김치찌개 500g", True),
            ("딸기우유", "서울우유 딸기우유 200mL", True),
            ("돼지고기 김치찌개", "종가집 김치찌개", False),
            ("탄산음료", "코카콜라 500ml", False),
        ]
        for recognized, product_name, expected in cases:
            with self.subTest(recognized=recognized, product=product_name):
                self.assertIs(is_credible_product_match(recognized, product_name), expected)
