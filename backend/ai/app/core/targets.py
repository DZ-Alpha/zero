"""개인 하루 목표(칼로리·당류) 계산. 저장된 목표값이 없을 때 신체정보로 계산한다.

계산식은 프론트엔드(SignupTargetForm.tsx)와 동일하게 맞춘다 — 값이 어긋나면
사용자가 회원가입 때 본 수치와 챗봇 답변이 달라지기 때문이다.
LLM이 계산하는 게 아니라 여기 코드가 계산하고, 결과 숫자만 프롬프트에 넣는다.
"""

# 활동량 문구 → 계수 (프론트 activityFactors와 동일)
_ACTIVITY_FACTORS = {
    "주로 앉아서 생활해요": 1.2,
    "가벼운 운동을 주 1~3회 해요": 1.375,
    "운동을 주 3~5회 해요": 1.55,
    "매일 활발하게 움직여요": 1.725,
}


def _round_to_ten(value: float) -> int:
    return round(value / 10) * 10


def calculate_targets(
    gender: str | None,
    age: int | None,
    height_cm: float | None,
    weight_kg: float | None,
    activity_level: str | None,
) -> tuple[int, int] | None:
    """(하루 칼로리, 하루 당류g)를 반환. 정보가 부족하면 None(계산 안 함)."""
    factor = _ACTIVITY_FACTORS.get(activity_level or "")
    if gender is None or age is None or height_cm is None or weight_kg is None or factor is None:
        return None

    # Harris-Benedict BMR (프론트 calculateBmr와 동일).
    # 성별은 DB 저장값(영문코드 MALE/FEMALE)과 프론트 표기(남성/여성)를 모두 인식한다.
    if gender in ("남성", "MALE"):
        bmr = 88.362 + 13.397 * weight_kg + 4.799 * height_cm - 5.677 * age
    else:  # 여성(FEMALE) 및 기타
        bmr = 447.593 + 9.247 * weight_kg + 3.098 * height_cm - 4.33 * age

    maintenance = _round_to_ten(_round_to_ten(bmr) * factor)
    sugar = round((maintenance * 0.1) / 4)  # 당 1g=4kcal, 총열량 10%
    return maintenance, sugar
