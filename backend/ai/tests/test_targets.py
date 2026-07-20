from app.core.targets import calculate_targets


def test_male_targets_match_frontend_formula():
    # 프론트 SignupTargetForm과 동일 공식: 남성 BMR = 88.362 + 13.397*w + 4.799*h - 5.677*age
    # 활동 "주로 앉아서 생활해요" → 계수 1.2
    r = calculate_targets(gender="남성", age=27, height_cm=180, weight_kg=70,
                          activity_level="주로 앉아서 생활해요")
    assert r is not None
    cal, sugar = r
    # BMR = 88.362 + 13.397*70 + 4.799*180 - 5.677*27 = 1740.8 → round10 = 1740
    # maintenance = round10(1740 * 1.2 = 2088) = 2090
    assert cal == 2090
    # sugar = round((2090 * 0.1)/4) = round(52.25) = 52
    assert sugar == 52


def test_female_targets_match_frontend_formula():
    r = calculate_targets(gender="여성", age=25, height_cm=165, weight_kg=55,
                          activity_level="가벼운 운동을 주 1~3회 해요")
    assert r is not None
    cal, sugar = r
    # 여성 BMR = 447.593 + 9.247*55 + 3.098*165 - 4.33*25 = 1358.9 → round10 = 1360
    # maintenance = round10(1360 * 1.375 = 1870) = 1870
    assert cal == 1870
    assert sugar == round((1870 * 0.1) / 4)  # 47


def test_missing_info_returns_none():
    # 성별·활동량 중 하나라도 없으면 계산 불가 → None
    assert calculate_targets(gender=None, age=27, height_cm=180, weight_kg=70,
                             activity_level="주로 앉아서 생활해요") is None
    assert calculate_targets(gender="남성", age=27, height_cm=180, weight_kg=70,
                             activity_level=None) is None
    assert calculate_targets(gender="남성", age=None, height_cm=180, weight_kg=70,
                             activity_level="주로 앉아서 생활해요") is None


def test_unknown_activity_returns_none():
    # 매핑에 없는 활동량 문구는 계산하지 않는다(잘못된 계수 방지).
    assert calculate_targets(gender="남성", age=27, height_cm=180, weight_kg=70,
                             activity_level="알 수 없는 값") is None


def test_english_gender_code_male_same_as_korean():
    # DB는 성별을 영문 코드(MALE/FEMALE)로 저장한다 — 한글과 동일하게 인식해야 함.
    kr = calculate_targets(gender="남성", age=27, height_cm=180, weight_kg=70,
                           activity_level="주로 앉아서 생활해요")
    en = calculate_targets(gender="MALE", age=27, height_cm=180, weight_kg=70,
                           activity_level="주로 앉아서 생활해요")
    assert en == kr == (2090, 52)


def test_english_gender_code_female():
    en = calculate_targets(gender="FEMALE", age=25, height_cm=165, weight_kg=55,
                           activity_level="가벼운 운동을 주 1~3회 해요")
    kr = calculate_targets(gender="여성", age=25, height_cm=165, weight_kg=55,
                           activity_level="가벼운 운동을 주 1~3회 해요")
    assert en == kr
