import re

_UNIT_ML = {"T": 15.0, "t": 5.0}


def parse_standard_unit(amount: str | None) -> tuple[float, str] | None:
    """amount 문자열에서 표준 조리단위(T/t/g/kg/ml/L)를 찾아
    (수치, "g" 또는 "ml")로 환산한다. 표준단위가 아니면 None."""
    if not amount:
        return None
    s = amount.strip()
    # 괄호 안의 부연설명(예: "63g (약 1/2개)")은 무시하고 앞부분만 본다
    s = re.split(r"[\(（]", s)[0].strip()

    m = re.match(r"^(\d+(?:\.\d+)?)\s*(kg|g|L|ml|T|t)$", s)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2)

    if unit == "kg":
        return (value * 1000.0, "g")
    if unit == "g":
        return (value, "g")
    if unit == "L":
        return (value * 1000.0, "ml")
    if unit == "ml":
        return (value, "ml")
    if unit in _UNIT_ML:
        return (value * _UNIT_ML[unit], "ml")
    return None
