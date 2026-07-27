from app.services.vision_analyzer import (
    StubVisionAnalyzer, build_analyzer, is_retryable, needs_confirmation, normalize_result,
)


def test_gemini_shape_normalizes():
    result = normalize_result(
        {"confidence": 0.87, "list-diet": [{"name": "비빔밥",
            "ingred-list": [{"name": "밥", "amount": 210}], "dang": 4.2, "calo": 560}]},
        provider="gemini")
    assert result["path"] == "food_photo_gemini"
    assert result["list-diet"][0]["name"] == "비빔밥"
    assert result["list-diet"][0]["calo"] == 560


def test_empty_list_diet_requires_confirmation():
    result = normalize_result({"confidence": 0.95, "list-diet": []}, provider="gemini")
    assert result["list-diet"] == []
    assert result["needs_user_confirmation"] is True


def test_invented_name_key_still_yields_item():
    payload = {"confidence": 0.95, "list-diet": [{
        "Korean food name": "모듬회", "ingred-list": [{"name": "연어", "amount": "60g"}],
        "dang": 0.1, "calo": 285}]}
    result = normalize_result(payload, provider="gemini")
    assert result["list-diet"][0]["name"] == "모듬회"
    assert result["list-diet"][0]["calo"] == 285


def test_amount_with_unit_suffix_parsed():
    result = normalize_result({"confidence": 0.9, "list-diet": [{
        "name": "비빔밥",
        "ingred-list": [{"name": "밥", "amount": "210g"}, {"name": "나물", "amount": "1.5 컵"},
                        {"name": "계란", "amount": "unknown"}],
        "dang": "4.2g", "calo": "560 kcal"}]}, provider="gemini")
    amounts = [i["amount"] for i in result["list-diet"][0]["ingred-list"]]
    assert amounts == [210, 1.5, 0]
    assert result["list-diet"][0]["dang"] == 4.2


def test_transient_errors_retryable():
    for code in ("GEMINI_HTTP_429", "GEMINI_HTTP_500", "GEMINI_UNAVAILABLE", "GEMINI_INVALID_JSON"):
        assert is_retryable(code) is True


def test_permanent_errors_not_retryable():
    for code in ("GEMINI_HTTP_400", "GEMINI_INVALID_RESPONSE", "IMAGE_TOO_LARGE"):
        assert is_retryable(code) is False


def test_needs_confirmation_threshold():
    result = normalize_result({"confidence": 0.4, "list-diet": [{"name": "된장찌개"}]}, provider="gemini")
    assert needs_confirmation(result, 0.75) is True
    assert needs_confirmation(result, 0.3) is False


def test_stub_analyzer_returns_food():
    result = StubVisionAnalyzer().analyze(b"x", "image/png")
    assert result["list-diet"][0]["name"]


class _S:
    vision_provider = "stub"
    gemini_api_key = ""
    gemini_model = "m"
    gemini_thinking_budget = 512
    gemini_max_output_tokens = 4096
    vision_timeout_seconds = 30.0


def test_build_analyzer_stub():
    assert isinstance(build_analyzer(_S()), StubVisionAnalyzer)


def test_build_analyzer_none_when_gemini_without_key():
    class G(_S):
        vision_provider = "gemini"
        gemini_api_key = ""
    assert build_analyzer(G()) is None
