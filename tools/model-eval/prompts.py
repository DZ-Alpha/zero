from datetime import date

from db import SampleProduct

# backend/product-service/app/services/ai_service.py의 generate_product_summary/
# generate_sweetener_description/generate_user_feature_info와 프롬프트를 동일하게
# 유지한다(PR-0301/0302/0303). 실제 서비스 프롬프트가 바뀌면 이 파일도 같이
# 맞춰야 비교 결과가 의미 있다 - 어긋나면 "다른 질문에 대한 답변"을 비교하는
# 셈이 된다.


def product_summary_prompt(product: SampleProduct) -> str:
    """PR-0301"""
    sweetener_names = [t.tag_name for t in product.sweetener_tags]
    allergen_names = [t.tag_name for t in product.allergen_tags]
    return (
        f"다음 제품을 소비자가 이해하기 쉽게 한 문장으로 요약해주세요.\n"
        f"제품명: {product.product_name}\n"
        f"브랜드: {product.brand_name or '미상'}\n"
        f"칼로리: {product.calories if product.calories is not None else '정보 없음'}kcal, "
        f"당류: {product.sugars if product.sugars is not None else '정보 없음'}g, "
        f"나트륨: {product.sodium if product.sodium is not None else '정보 없음'}mg\n"
        f"대체 당: {', '.join(sweetener_names) if sweetener_names else '없음'}\n"
        f"알레르기 유발 성분: {', '.join(allergen_names) if allergen_names else '없음'}\n"
        f"원재료: {product.ingredient_text or '정보 없음'}\n"
        f"한 문장으로만 답하세요."
    )


def sweetener_description_prompt(product: SampleProduct) -> str | None:
    """PR-0302. 감미료 태그가 없는 상품이면 실제 서비스처럼 호출 자체를 생략한다."""
    sweetener_tags = product.sweetener_tags
    if not sweetener_tags:
        return None

    descriptions = []
    for tag in sweetener_tags:
        desc = tag.description or tag.tag_name
        caution = f" 주의: {tag.caution_text}" if tag.caution_text else ""
        descriptions.append(f"{tag.tag_name}: {desc}{caution}")

    return (
        f"다음은 '{product.product_name}'에 들어간 대체 당 성분들입니다.\n"
        + "\n".join(descriptions)
        + "\n소비자가 이해하기 쉽도록 각 성분을 2~3문장으로 설명해주세요."
    )


def user_feature_info_prompt(
    product: SampleProduct,
    birth_year: int | None,
    gender: str | None,
    daily_calorie_target: float | None,
    daily_sugar_target_g: float | None,
) -> str:
    """PR-0303"""
    current_year = date.today().year
    age = (current_year - birth_year) if birth_year else None
    age_str = f"{age}세" if age else "나이 정보 없음"
    gender_str = gender or "성별 정보 없음"

    allergen_names = [t.tag_name for t in product.allergen_tags]
    calorie_pct = (
        f"{product.calories / daily_calorie_target * 100:.1f}%"
        if product.calories and daily_calorie_target
        else "정보 없음"
    )
    sugar_pct = (
        f"{product.sugars / daily_sugar_target_g * 100:.1f}%"
        if product.sugars and daily_sugar_target_g
        else "정보 없음"
    )

    return (
        f"사용자 정보: {age_str}, {gender_str}\n"
        f"제품명: {product.product_name}\n"
        f"이 제품 1회 섭취 시 일일 권장 칼로리의 {calorie_pct}, 당류의 {sugar_pct}를 섭취하게 됩니다.\n"
        f"주의 알레르기 성분: {', '.join(allergen_names) if allergen_names else '없음'}\n"
        f"사용자 눈높이에 맞춰 2~3문장으로 쉽게 설명해주세요."
    )
