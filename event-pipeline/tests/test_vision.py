from __future__ import annotations

import unittest

from app.vision import StubVisionProvider, is_retryable, needs_confirmation, normalize_result


class VisionResultTests(unittest.TestCase):
    def test_gemini_shape_normalizes_to_public_contract(self) -> None:
        result = normalize_result({"confidence": 0.87, "list-diet": [{"name": "비빔밥", "ingred-list": [{"name": "밥", "amount": 210}], "dang": 4.2, "calo": 560}]}, provider="gemini")
        self.assertEqual(result["path"], "food_photo_gemini")
        self.assertEqual(result["list-diet"][0]["name"], "비빔밥")
        self.assertEqual(result["list-diet"][0]["calo"], 560)
        self.assertEqual(result["confidence"], 0.87)

    def test_foodlens_common_shape_normalizes(self) -> None:
        result = normalize_result({"data": {"foods": [{"foodName": "김치찌개", "nutrition": {"sugar": "3.5", "calories": "210"}}]}}, provider="foodlens")
        self.assertEqual(result["list-diet"][0]["dang"], 3.5)
        self.assertEqual(result["list-diet"][0]["calo"], 210)

    def test_stub_contract(self) -> None:
        result = StubVisionProvider().analyze(image=b"x", content_type="image/png", image_key="x.png")
        self.assertEqual(result["list-diet"][0]["name"], "검증용 음식")

    def test_empty_list_diet_requires_confirmation_despite_high_confidence(self) -> None:
        """Gemini has returned {"confidence": 0.95, "list-diet": []} on real photos."""
        result = normalize_result({"confidence": 0.95, "list-diet": []}, provider="gemini")
        self.assertEqual(result["list-diet"], [])
        self.assertTrue(result["needs_user_confirmation"])
        self.assertTrue(needs_confirmation(result, 0.75))

    def test_low_confidence_requires_confirmation(self) -> None:
        result = normalize_result({"confidence": 0.4, "list-diet": [{"name": "된장찌개"}]}, provider="gemini")
        self.assertTrue(needs_confirmation(result, 0.75))
        self.assertFalse(needs_confirmation(result, 0.3))

    def test_confident_non_empty_result_needs_no_confirmation(self) -> None:
        result = normalize_result({"confidence": 0.95, "list-diet": [{"name": "비빔밥"}]}, provider="gemini")
        self.assertFalse(result["needs_user_confirmation"])


class ModelKeyDriftTests(unittest.TestCase):
    """Real Gemini replies that the normalizer used to discard."""

    def test_invented_name_key_still_yields_the_item(self) -> None:
        payload = {"confidence": 0.95, "list-diet": [{
            "Korean food name": "모듬회",
            "ingred-list": [{"name": "연어", "amount": "60g"}, {"name": "참치", "amount": "50g"}],
            "dang": 0.1, "calo": 285,
        }]}
        result = normalize_result(payload, provider="gemini")
        self.assertEqual(len(result["list-diet"]), 1)
        item = result["list-diet"][0]
        self.assertEqual(item["name"], "모듬회")
        self.assertEqual(item["calo"], 285)
        self.assertFalse(result["needs_user_confirmation"])

    def test_amount_with_unit_suffix_is_parsed(self) -> None:
        result = normalize_result({"confidence": 0.9, "list-diet": [{
            "name": "비빔밥",
            "ingred-list": [{"name": "밥", "amount": "210g"}, {"name": "나물", "amount": "1.5 컵"},
                            {"name": "계란", "amount": "unknown"}],
            "dang": "4.2g", "calo": "560 kcal",
        }]}, provider="gemini")
        amounts = [i["amount"] for i in result["list-diet"][0]["ingred-list"]]
        self.assertEqual(amounts, [210, 1.5, 0])
        self.assertEqual(result["list-diet"][0]["dang"], 4.2)
        self.assertEqual(result["list-diet"][0]["calo"], 560)

    def test_item_without_any_name_is_still_dropped(self) -> None:
        result = normalize_result({"confidence": 0.9, "list-diet": [{"calo": 100}]}, provider="gemini")
        self.assertEqual(result["list-diet"], [])
        self.assertTrue(result["needs_user_confirmation"])


class RetryClassificationTests(unittest.TestCase):
    def test_transient_provider_errors_are_retryable(self) -> None:
        for code in ("GEMINI_HTTP_429", "GEMINI_HTTP_500", "GEMINI_HTTP_503", "GEMINI_UNAVAILABLE", "FOODLENS_UNAVAILABLE"):
            self.assertTrue(is_retryable(code), code)

    def test_mangled_model_output_is_retryable(self) -> None:
        """Observed sporadically: roughly 1 photograph in 40, not reproducible."""
        for code in ("GEMINI_INVALID_JSON", "FOODLENS_INVALID_RESPONSE"):
            self.assertTrue(is_retryable(code), code)

    def test_permanent_errors_are_not_retryable(self) -> None:
        # GEMINI_INVALID_RESPONSE means the envelope carried no candidate at
        # all, which a safety block reproduces on every attempt.
        for code in ("GEMINI_HTTP_400", "GEMINI_HTTP_403", "GEMINI_INVALID_RESPONSE", "IMAGE_TOO_LARGE", "IMAGE_EMPTY", "OBJECT_NOT_READABLE", "INVALID_EVENT"):
            self.assertFalse(is_retryable(code), code)
