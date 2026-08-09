from unittest import TestCase

from app.services.swap_rules import (
    is_already_low_sugar,
    is_valid_swap_candidate,
    serving_key,
)


class DietSwapFilterTests(TestCase):
    def setUp(self) -> None:
        self.source = {
            "name": "카라멜 팝콘",
            "category": "베이커리·간식",
            "foodType": "팝콘",
            "serving": "100.000g",
            "sugar": 18.5,
            "tags": ["CATEGORY_SNACK"],
        }
        self.candidate = {"id": "candidate", "sugar": 3.0, "similarity": 0.82}
        self.detail = {
            "category": "베이커리·간식",
            "foodType": "팝콘",
            "serving": "100g",
        }

    def test_accepts_same_food_type_unit_and_meaningful_reduction(self) -> None:
        self.assertTrue(is_valid_swap_candidate(self.source, self.candidate, self.detail))

    def test_rejects_different_detailed_food_type(self) -> None:
        self.detail["foodType"] = "쿠키"
        self.assertFalse(is_valid_swap_candidate(self.source, self.candidate, self.detail))

    def test_rejects_mismatched_comparison_unit(self) -> None:
        self.detail["serving"] = "100mL"
        self.assertFalse(is_valid_swap_candidate(self.source, self.candidate, self.detail))

    def test_rejects_low_similarity_or_trivial_reduction(self) -> None:
        self.candidate["similarity"] = 0.69
        self.assertFalse(is_valid_swap_candidate(self.source, self.candidate, self.detail))
        self.candidate.update({"similarity": 0.82, "sugar": 18.1})
        self.assertFalse(is_valid_swap_candidate(self.source, self.candidate, self.detail))

    def test_excludes_products_already_marked_low_or_zero(self) -> None:
        self.assertTrue(is_already_low_sugar({**self.source, "name": "저당 카라멜 팝콘"}))
        self.assertTrue(is_already_low_sugar({**self.source, "name": "제로 팝콘"}))
        self.assertTrue(is_already_low_sugar({**self.source, "sugar": 0}))
        self.assertFalse(is_already_low_sugar(self.source))

    def test_serving_key_normalizes_decimal_but_not_unit(self) -> None:
        self.assertEqual(serving_key("100.000g"), "100g")
        self.assertEqual(serving_key("100 mL"), "100ml")
        self.assertNotEqual(serving_key("100g"), serving_key("100mL"))
