from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)


class VisionProviderError(RuntimeError):
    """A provider error that is safe to expose as a short worker failure code."""


class GeminiVisionAnalyzer:
    def __init__(self, api_key: str, model: str, timeout_seconds: float,
                 thinking_budget: int = 512, max_output_tokens: int = 4096) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._thinking_budget = thinking_budget
        self._max_output_tokens = max_output_tokens

    def analyze(self, image_bytes: bytes, media_type: str) -> dict:
        generation_config = {
            "temperature": 0,
            "responseMimeType": "application/json",
            "maxOutputTokens": self._max_output_tokens,
        }
        if self._thinking_budget >= 0:
            generation_config["thinkingConfig"] = {"thinkingBudget": self._thinking_budget}
        payload = {
            "contents": [{"parts": [
                {"text": _GEMINI_PROMPT},
                {"inline_data": {"mime_type": media_type,
                                 "data": base64.b64encode(image_bytes).decode("ascii")}},
            ]}],
            "generationConfig": generation_config,
        }
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"
        response = _post_json(endpoint, payload, {"X-goog-api-key": self._api_key}, self._timeout)
        try:
            text = "".join(
                part.get("text", "")
                for candidate in response["candidates"]
                for part in candidate["content"]["parts"]
                if isinstance(part, dict)
            )
        except (KeyError, TypeError) as exc:
            raise VisionProviderError("GEMINI_INVALID_RESPONSE") from exc
        return normalize_result(_parse_json_text(text), provider="gemini")


class StubVisionAnalyzer:
    def analyze(self, image_bytes: bytes, media_type: str) -> dict:
        return {"path": "food_photo_stub",
                "list-diet": [{"name": "검증용 음식",
                               "ingred-list": [{"name": "탄수화물", "amount": 0}],
                               "dang": 0, "calo": 0}],
                "confidence": 0.0, "needs_user_confirmation": True}


def normalize_result(payload: Any, *, provider: str) -> dict[str, Any]:
    """Map provider output into the public diet API's stable list-diet shape."""
    if not isinstance(payload, dict):
        raise VisionProviderError(f"{provider.upper()}_INVALID_RESPONSE")
    normalized: list[dict[str, Any]] = []
    dropped: list[list[str]] = []
    for item in _find_items(payload):
        if not isinstance(item, dict):
            continue
        name = _item_name(item)
        if not name and isinstance(item.get("food"), dict):
            name = _item_name(item["food"])
        if not name:
            # Dropping silently is how a whole recognised meal disappeared before.
            dropped.append(sorted(item)[:6])
            continue
        nutrients = item.get("nutrition") if isinstance(item.get("nutrition"), dict) else item
        ingredients = item.get("ingred-list", item.get("ingredients", []))
        if not isinstance(ingredients, list):
            ingredients = []
        normalized.append({
            "name": name[:120],
            "ingred-list": [{"name": str(ingredient.get("name", "재료"))[:120], "amount": _number(ingredient.get("amount"))} for ingredient in ingredients if isinstance(ingredient, dict)],
            "dang": _number(_first_value(nutrients, "dang", "sugar", "sugars", "sugar_g")),
            "calo": _number(_first_value(nutrients, "calo", "calorie", "calories", "kcal", "energy")),
        })
    if dropped:
        logger.warning("%s returned %s item(s) with no recognisable name key: %s",
                       provider, len(dropped), dropped)
    confidence = _confidence(_first_value(payload, "confidence", "confidence_score", "score"))
    result = {
        "path": f"food_photo_{provider}",
        "list-diet": normalized,
        "confidence": confidence,
        "confidence_source": "provider" if provider == "foodlens" else "model_self_assessment",
    }
    result["needs_user_confirmation"] = needs_confirmation(result, DEFAULT_CONFIDENCE_THRESHOLD)
    return result


DEFAULT_CONFIDENCE_THRESHOLD = 0.75


def needs_confirmation(result: dict[str, Any], threshold: float) -> bool:
    """A draft needs user confirmation when the model is unsure *or* found no food.

    Gemini does not reliably follow the prompt's "return confidence 0.0 for a
    non-food image" instruction; it has returned an empty list-diet alongside a
    0.95 confidence. Confidence alone therefore cannot gate the UX.
    """
    if not result.get("list-diet"):
        return True
    return float(result.get("confidence", 0)) < threshold


# A reply the model mangled is not reproducible: a photograph that failed to
# parse once has since parsed correctly on five consecutive calls, so these are
# worth another attempt rather than a permanent failure.
_RETRYABLE_OUTPUT_CODES = frozenset({"GEMINI_INVALID_JSON", "FOODLENS_INVALID_RESPONSE"})


def is_retryable(error_code: str) -> bool:
    """Whether a provider failure may succeed on a later attempt."""
    if error_code.endswith("_UNAVAILABLE") or error_code in _RETRYABLE_OUTPUT_CODES:
        return True
    match = re.search(r"_HTTP_(\d{3})$", error_code)
    if not match:
        return False
    status = int(match.group(1))
    return status == 429 or 500 <= status <= 599


# The key names are spelled out because the model has been observed turning a
# descriptive phrase into the key itself, e.g. {"Korean food name": "모듬회"}.
_GEMINI_PROMPT = (
    "Analyze this meal photograph. Return JSON only, no Markdown.\n"
    "Use exactly this schema, with these literal key names:\n"
    '{"confidence": <number 0-1>, "list-diet": ['
    '{"name": <string>, "ingred-list": [{"name": <string>, "amount": <number>}], '
    '"dang": <number>, "calo": <number>}]}\n'
    'The "name" value is the food\'s Korean name. Do not rename any key.\n'
    '"amount" is grams as a bare number with no unit suffix. '
    '"dang" is estimated sugar in grams. "calo" is estimated kcal. '
    "Use 0 when a number is unknown.\n"
    "Include only food that is visible. If the image contains no food, return "
    '{"confidence": 0.0, "list-diet": []}.\n'
    "Do not identify people or infer health facts."
)


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    request = Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json", "Accept": "application/json", **headers}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            decoded = json.loads(response.read())
    except HTTPError as exc:
        raise VisionProviderError(f"GEMINI_HTTP_{exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise VisionProviderError("GEMINI_UNAVAILABLE") from exc
    if not isinstance(decoded, dict):
        raise VisionProviderError("GEMINI_INVALID_RESPONSE")
    return decoded


def _parse_json_text(value: str) -> dict[str, Any]:
    value = value.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.IGNORECASE)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise VisionProviderError("GEMINI_INVALID_JSON") from exc
    if not isinstance(parsed, dict):
        raise VisionProviderError("GEMINI_INVALID_JSON")
    return parsed


def _find_items(payload: dict[str, Any]) -> list[Any]:
    for container in (payload, payload.get("result"), payload.get("data"), payload.get("body")):
        if isinstance(container, dict):
            for key in ("list-diet", "foods", "foodList", "food_list", "results", "recognitionResults"):
                if isinstance(container.get(key), list):
                    return container[key]
    return []


def _first_value(value: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in value:
            return value[key]
    return 0


def _first_text(value: dict[str, Any], *keys: str) -> str:
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _item_name(item: dict[str, Any]) -> str:
    """Read a food name, tolerating a model that invents its own key.

    Gemini has answered with {"Korean food name": "모듬회"} instead of "name",
    which silently discarded the whole recognised item, so any string-valued key
    that reads like a name is accepted as a fallback.
    """
    name = _first_text(item, "name", "food_name", "foodName", "displayName")
    if name:
        return name
    for key, value in item.items():
        if "name" in key.lower() and isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _number(value: Any) -> float | int:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        # Models answer with units attached, e.g. "60g" or "1.5 컵".
        if isinstance(value, str):
            match = re.match(r"\s*(-?\d+(?:\.\d+)?)", value)
            if match:
                return _number(match.group(1))
        return 0
    if numeric != numeric or numeric in (float("inf"), float("-inf")):
        return 0
    return int(numeric) if numeric.is_integer() else round(numeric, 2)


def _confidence(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if score > 1:
        score /= 100
    return round(min(1.0, max(0.0, score)), 3)


def build_analyzer(settings):
    """provider=stub면 Stub, gemini+키 있으면 Gemini, gemini+키 없으면 None(준비중 폴백)."""
    provider = (settings.vision_provider or "gemini").lower()
    if provider == "stub":
        return StubVisionAnalyzer()
    if provider == "gemini":
        if not settings.gemini_api_key:
            return None
        return GeminiVisionAnalyzer(
            settings.gemini_api_key, settings.gemini_model, settings.vision_timeout_seconds,
            settings.gemini_thinking_budget, settings.gemini_max_output_tokens,
        )
    return None
