import re


_LOW_SUGAR_LABELS = ("저당", "제로", "무가당", "무설탕", "sugarfree", "sugar-free")
_MIN_SWAP_SIMILARITY = 0.70


def compact_product_name(value: object) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", str(value or "").lower())


def is_credible_product_match(recognized_name: str, product_name: object) -> bool:
    """Vision의 일반 음식명으로 엉뚱한 가공식품을 추천하지 않는다."""
    recognized = compact_product_name(recognized_name)
    product = compact_product_name(product_name)
    return len(recognized) >= 2 and (recognized in product or product in recognized)


def is_already_low_sugar(product: dict[str, object]) -> bool:
    labels = " ".join(
        [str(product.get("name") or ""), *(str(tag) for tag in product.get("tags") or [])]
    ).lower().replace(" ", "")
    return float(product.get("sugar") or 0) <= 0 or any(label in labels for label in _LOW_SUGAR_LABELS)


def serving_key(value: object) -> str | None:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(g|ml)\s*", str(value or ""), re.IGNORECASE)
    if not match:
        return None
    return f"{float(match.group(1)):g}{match.group(2).lower()}"


def is_valid_swap_candidate(
    source: dict[str, object],
    candidate: dict[str, object],
    detail: dict[str, object],
) -> bool:
    source_sugar = float(source.get("sugar") or 0)
    candidate_sugar = float(candidate.get("sugar") or 0)
    saved = source_sugar - candidate_sugar
    saved_pct = (saved / source_sugar * 100) if source_sugar > 0 else 0

    return all(
        (
            source.get("foodType") is not None,
            source.get("foodType") == detail.get("foodType"),
            source.get("category") == detail.get("category"),
            serving_key(source.get("serving")) is not None,
            serving_key(source.get("serving")) == serving_key(detail.get("serving")),
            float(candidate.get("similarity") or 0) >= _MIN_SWAP_SIMILARITY,
            candidate_sugar < source_sugar,
            saved >= 0.5,
            saved >= 2 or saved_pct >= 20,
        )
    )
