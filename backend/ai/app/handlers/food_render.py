from app.schemas import UserContext

_RETRY = "사진에서 음식을 찾지 못했어요. 음식이 잘 보이게 다시 찍어주시겠어요?"


def _names(items: list[dict]) -> str:
    return ", ".join(str(i.get("name", "")) for i in items if i.get("name"))


def _sum(items: list[dict], key: str) -> float:
    total = 0.0
    for i in items:
        try:
            total += float(i.get(key) or 0)
        except (TypeError, ValueError):
            continue
    return round(total, 1)


def _target_clause(total_dang: float, context: UserContext) -> str:
    target = context.daily_sugar_target_g
    if not target:
        return ""
    if total_dang >= target * 0.8:
        return f" 하루 당류 목표({target}g)에 거의 근접하니 주의하세요."
    return f" 하루 당류 목표({target}g)에는 아직 여유가 있어요."


def render_food_analysis(result: dict, context: UserContext) -> str:
    items = result.get("list-diet") or []
    if not items:
        return _RETRY

    total_dang = _sum(items, "dang")
    total_calo = _sum(items, "calo")
    hedged = bool(result.get("needs_user_confirmation"))

    if len(items) == 1:
        name = items[0].get("name", "음식")
        if hedged:
            return (f"{name}로 보이는데 확실하진 않아요. 당류는 약 {total_dang}g으로 추정돼요. "
                    "정확한 수치는 포장지 표시를 확인해 주세요.")
        body = f"{name}네요! 당류는 약 {total_dang}g, 열량은 약 {total_calo}kcal로 보여요."
        return body + _target_clause(total_dang, context)

    prefix = "사진에서 " + _names(items) + "를 확인했어요."
    if hedged:
        return prefix + f" 합쳐서 당류 약 {total_dang}g으로 추정돼요. 정확한 수치는 표시를 확인해 주세요."
    body = prefix + f" 합쳐서 당류 약 {total_dang}g, 열량 약 {total_calo}kcal예요."
    return body + _target_clause(total_dang, context)
