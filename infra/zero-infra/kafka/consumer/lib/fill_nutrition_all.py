# -*- coding: utf-8 -*-
"""레시피 재료(recipe_ingredients)의 sugar_g/kcal을 AWS Bedrock(Claude)으로 채운다.

ingredient_type='common'인 재료만 채우고, 'substituted'(저당/제로 대체재)는
건드리지 않는다. common 재료는 raw_ingredient_nutrients.csv에서 후보를 찾아
계산하되, 후보가 없으면 LLM의 일반 영양 지식으로 채운다(null을 남기지 않음).

주기적으로 새로 수집한 레시피에 재사용할 수 있도록 CSV 경로를 인자로 받는다.

사용법:
    # 전체 처리 (기본):
    python fill_nutrition_all.py <ingredients.csv> <recipes.csv> <raw_nutrients.csv>

    # 한 번에 N개 레시피만 처리하고 멈추기(재개 가능, 사람이 중간 검증할 때):
    python fill_nutrition_all.py <ingredients.csv> <recipes.csv> <raw_nutrients.csv> --batch 100

    # 동시 처리 수 조절(기본 1; Bedrock 분당 5회 제한 때문에 크게 올려도 이득 적음):
    python fill_nutrition_all.py <ingredients.csv> <recipes.csv> <raw_nutrients.csv> --workers 4

동작 방식:
- 재개(resume): 레시피의 common 재료가 전부(sugar_g와 kcal 둘 다) 채워졌으면
  완료로 간주하고 건너뛴다. 중간에 멈춰도 다시 실행하면 이어서 처리한다.
- 기존값 보존: 이미 채워진 common 재료는 재계산해 덮어쓰지 않고, 비어있던 것만 채운다.
- ingredients CSV는 매 레시피 처리 후 즉시 전체를 다시 써서 중단 안전성을 확보한다.

의존성: boto3, 그리고 AWS 자격증명(Bedrock InvokeModel 권한).
"""
import argparse
import csv
import difflib
import json
import re
import shutil
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import boto3

sys.stdout.reconfigure(errors="replace")

# ---------------------------------------------------------------------------
# Bedrock 설정 및 레이트 리미터
# ---------------------------------------------------------------------------
BEDROCK_MODEL_ID = "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"
BEDROCK_REGION = "ap-northeast-2"
_bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

# AWS 계정 할당량: Claude 3.5 Sonnet V2 cross-region inference는 분당 5회로
# 제한되어 있음(Service Quotas, 조정 불가). 넘기면 ThrottlingException이 나므로
# 요청 사이 최소 간격(12초)을 락으로 보장한다.
MIN_REQUEST_INTERVAL_SEC = 60.0 / 5.0
_rate_lock = threading.Lock()
_last_request_time = [0.0]


def _wait_for_rate_limit():
    with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time[0]
        if elapsed < MIN_REQUEST_INTERVAL_SEC:
            time.sleep(MIN_REQUEST_INTERVAL_SEC - elapsed)
        _last_request_time[0] = time.monotonic()


INGREDIENTS_FIELDS = ["id", "recipe_id", "name", "amount", "ingredient_type", "sugar_g", "kcal"]

# ---------------------------------------------------------------------------
# 프롬프트
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """당신은 레시피 재료의 영양값(당류/칼로리)을 계산하는 도구입니다.
여기 입력되는 재료는 전부 ingredient_type='common'인 일반 재료이며, 저당/제로
대체재(substituted)는 애초에 입력에서 제외되어 있습니다. 따라서 **모든 재료의
sugar_g/kcal을 반드시 채워야 합니다. null을 반환하지 마세요.**

각 재료마다 raw_ingredient_nutrients 후보 목록(food_code=name
per100_sugar_g=... per100_kcal=... 형식, 100g/100ml 기준 영양값)이 제공될 수도,
"후보 없음"일 수도 있습니다. 레시피의 조리 단계(steps)를 참고해 그 재료가 실제로
어떤 상태(생것/데친것/볶은것/구운것/다진것 등)로 쓰였는지 판단하고 가장 적합한
항목을 고르세요.

계산 방법 (반드시 이 순서로 계산하세요):
1. amount를 g(또는 ml, 1ml≈1g으로 취급)으로 환산하세요. 이미 g/ml 단위면
   **그 숫자를 그대로 사용하세요**(예: "50g"이면 50g, 절대 100g으로 반올림하거나
   "1개≈150g" 같은 개수 추정으로 바꾸지 마세요). "50~60g"이나 "200~250ml"처럼
   범위로 주어지면 중앙값을 쓰세요(55g, 225ml). "300g / 1모"처럼 슬래시로 두 표기가
   병기돼 있으면 g/ml 쪽을 우선 사용하세요. T(큰술)=15g, t(작은술)=5g처럼 표준
   조리단위는 정확히 환산하고, "1개"/"약간"/"반개"/"취향껏"/"적당량"처럼 비표준·모호
   단위만 재료 종류와 문맥을 고려해 합리적인 g으로 추정하세요. amount가 비어있거나
   "취향껏"이어도 null로 두지 말고, 그 재료를 그 표현으로 쓸 때 통상 어느 정도
   양인지 추정해 계산하세요(예: "소금 약간"≈0.5g, "올리브유 적당량"≈5g).
2. 영양값의 출처는 다음 우선순위로 정하세요:
   (a) 후보 목록에 그 재료와 의미적으로 일치하는 항목이 있으면, 그 후보의
       per100_sugar_g/per100_kcal에 (환산한 g수 / 100)을 곱해 계산하세요.
       **후보에 제공된 실제 수치를 그대로 쓰고, 100g당 값을 그대로 반환하지
       말고 반드시 실사용량 기준으로 축소 계산하세요.**
       예: 후보 "참기름_참깨_압착착유한것: per100_sugar_g=0.0 per100_kcal=897.0",
       amount 4g이면 sugar_g = 0.0*4/100 = 0.0, kcal = 897.0*4/100 = 35.9
   (b) 후보 목록에 적합한 항목이 없거나 "후보 없음"이면, 당신이 알고 있는 그
       재료의 공인/일반 100g 기준 당류·칼로리 지식을 사용해 같은 방식으로
       (환산 g수/100)을 곱해 계산하세요. 이때도 100g당 값을 그대로 넣지 말고
       실사용량 기준으로 축소 계산하세요. (예: 두부 100g당 kcal≈80, "닭가슴살"
       100g당 kcal≈110 등 잘 알려진 값 사용)

주의:
- **후보가 단 1개뿐이어도 문자열만 보고 자동 채택하지 마세요.** 후보 이름과
  재료명이 실제로 같은 식품인지 의미를 재확인하세요. 특히 합성어 함정에 주의 —
  예: "두유"의 후보로 "호두유"(호두 기름, 두유와 전혀 다른 식품) 하나만 왔다면
  그 후보를 쓰지 말고, 대신 (b)의 일반 지식(두유의 실제 영양값)으로 계산하세요.
  반대로 "대파"의 후보 "파_대파_생것"처럼 실제로 동일한 식품이면 정상 채택하세요.
- 어떤 경우에도 sugar_g/kcal을 null로 남기지 마세요. 후보가 없으면 (b)로,
  정량이 모호하면 추정으로, 항상 숫자를 채우세요.

입력의 각 재료에는 [1], [2] 같은 고유 번호가 붙어 있습니다. 같은 이름의 재료가
여러 번 나올 수 있으므로(예: "우유 100ml"와 "우유 190ml"), **반드시 입력에 있는
모든 번호 각각에 대해 하나씩** 응답하고, 응답의 idx에 그 번호를 그대로 적으세요.
서로 다른 번호는 수량이 다를 수 있으니 각자의 수량으로 따로 계산하세요. 번호를
합치거나 누락하지 마세요.

다음 JSON 형식으로만 응답하세요 (설명 문구 없이 JSON만):
{
  "ingredients": [
    {"idx": 번호(입력의 [n]과 동일), "name": "재료명(입력과 동일하게)",
     "food_code": "매칭된 코드 또는 null(일반지식 사용 시)", "sugar_g": 숫자, "kcal": 숫자}
  ]
}
"""


# ---------------------------------------------------------------------------
# 재료명 ↔ raw_ingredient_nutrients 후보 매칭
# ---------------------------------------------------------------------------
_PROCESSING_PREFIXES = ["다진", "다져진", "썬", "채썬", "간", "으깬", "삶은", "구운", "볶은"]
_QUALIFIER_WORDS = ["약간의", "약", "반", "저당", "무가당", "국내산", "냉동"]

# 공백 없이 붙여쓴 접두어를 벗길 때만 쓰는 목록. "간"은 "간 마늘"(갈다)과 "간장"
# (조미료 명사)에 동시에 등장하는 동음이의라, 공백 없는 벗기기에 포함시키면
# "간장"이 "장"으로 잘못 잘린다. 공백 있는 "간 마늘"은 토큰이 이미 분리되므로
# _PROCESSING_PREFIXES 쪽(공백 기준 필터)에는 "간"을 그대로 둔다.
_CONCAT_PROCESSING_PREFIXES = [p for p in _PROCESSING_PREFIXES if p != "간"]

_SHORT_CORE_LENGTH = 2  # 이 길이 이하 핵심어는 완전 일치 위주(아래 _match_segment 참조)


def extract_core_token(name: str) -> str:
    """재료명에서 처리동사 접두어/수식어를 제거해 raw와 비교할 핵심 명사를 뽑는다.
    형태소 분석이 아니라 1차 필터용 휴리스틱이며, 최종 판단은 LLM이 후보를 보고 한다.
    "다진 마늘"(공백)뿐 아니라 "다진마늘"(공백 없음)도 접두어를 벗겨 "마늘"로 만든다."""
    tokens = name.strip().split()
    filtered = [t for t in tokens if t not in _PROCESSING_PREFIXES and t not in _QUALIFIER_WORDS]
    core = filtered[-1] if filtered else name.strip()
    for prefix in _CONCAT_PROCESSING_PREFIXES:
        if len(core) > len(prefix) and core.startswith(prefix):
            core = core[len(prefix):]
            break
    return core


def _match_segment(core: str, segment: str) -> bool:
    """core와 raw_name의 한 세그먼트가 부분 포함 관계이면서 짧은-길이 노이즈 규칙을
    통과하면 True. 1글자가 관여하는 매칭("간"↔"간장", "파"↔"파인애플")은 완전 일치만
    허용해 노이즈를 막고, 2글자끼리는 길이차 1까지 허용("간장"↔"국간장")한다."""
    if not (core in segment or segment in core):
        return False
    min_len = min(len(core), len(segment))
    if min_len == 1:
        return len(segment) == len(core)
    if min_len <= _SHORT_CORE_LENGTH:
        return abs(len(segment) - len(core)) <= 1
    return True


def narrow_candidates(ingredient_name: str, raw_rows: list, limit: int = 30) -> list:
    """raw_rows(각 dict가 'name' 키를 가짐) 중 ingredient_name과 관련된 상위 limit개.

    raw_ingredient_nutrients 이름은 "재료명_부위_처리상태" 패턴이라, 사용자가 쓰는
    재료명이 head(첫 세그먼트)가 아니라 2번째 이후 세그먼트와 일치하는 경우가 흔하다
    (예: "닭가슴살"→"닭고기_가슴...", "백미"→"멥쌀_백미_생것"). 그래서 raw_name을
    '_'로 나눈 모든 세그먼트(괄호 앞부분까지)를 core와 비교하고, 하나라도 통과하면
    후보로 채택한다. 세그먼트 자체가 사용자 표현과 다른 동의어("닭고기_가슴")여도
    후보 0개가 될 수 있으나, 그 경우 LLM이 일반 지식으로 채우므로 문제되지 않는다."""
    core = extract_core_token(ingredient_name)
    scored = []
    for row in raw_rows:
        best_score = None
        for seg in row["name"].split("_"):
            segment = re.split(r"\(", seg)[0]
            if not segment or not _match_segment(core, segment):
                continue
            score = difflib.SequenceMatcher(None, core, segment).ratio()
            if best_score is None or score > best_score:
                best_score = score
        if best_score is not None:
            scored.append((best_score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:limit]]


# ---------------------------------------------------------------------------
# 프롬프트 생성 / 응답 파싱 / LLM 호출
# ---------------------------------------------------------------------------
def build_prompt(recipe_name, steps, ingredients, candidates_by_ingredient) -> str:
    """재료마다 [1],[2]... 고유 번호(입력 순서)를 붙여 프롬프트를 만든다. 같은 이름
    재료가 여러 개여도 번호로 구분되므로 응답을 번호로 1:1 매칭할 수 있다."""
    lines = [f"레시피명: {recipe_name}", "", "조리 단계:"]
    for i, step in enumerate(steps, 1):
        lines.append(f"{i}. {step}")
    lines.append("")
    lines.append("재료 목록 및 매칭 후보:")
    for idx, ing in enumerate(ingredients, 1):
        name = ing["name"]
        amount = ing.get("amount") or "(정량 없음)"
        itype = ing.get("ingredient_type", "common")
        lines.append(f"[{idx}] {name} | 수량: {amount} | 분류: {itype}")
        candidates = candidates_by_ingredient.get(name, [])
        if candidates:
            cand_parts = [
                f"{c['food_code']}={c['name']} "
                f"(per100_sugar_g={c.get('per100_sugar_g', '')} per100_kcal={c.get('per100_kcal', '')})"
                for c in candidates
            ]
            lines.append(f"  후보: {', '.join(cand_parts)}")
        else:
            lines.append("  후보 없음")
    return "\n".join(lines)


def parse_fill_response(raw: str) -> list:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1]
        s = s.rsplit("```", 1)[0]
    return json.loads(s).get("ingredients", [])


def call_fill_llm(recipe_name, steps, ingredients, candidates_by_ingredient) -> list:
    prompt = build_prompt(recipe_name, steps, ingredients, candidates_by_ingredient)
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    })
    _wait_for_rate_limit()
    resp = _bedrock.invoke_model(modelId=BEDROCK_MODEL_ID, body=body)
    result = json.loads(resp["body"].read())
    text_blocks = [b["text"] for b in result["content"] if b.get("type") == "text"]
    return parse_fill_response("".join(text_blocks))


# ---------------------------------------------------------------------------
# 레시피 1건 처리 (substituted 제외, common만 채움, idx 매칭)
# ---------------------------------------------------------------------------
def _normalize_name(s: str) -> str:
    s = s.replace("​", "").strip()  # 제로폭 공백 제거
    s = re.sub(
        r"\s*\d[\d./~\s]*(g|kg|ml|l|개|장|모|컵|스푼|큰술|작은술|T|t|줄|줄기|마리|봉|봉지|알|쪽|대)?\s*$",
        "", s,
    )
    return re.sub(r"\s+", "", s)


def process_recipe(recipe, recipe_ingredients, raw_rows) -> dict:
    """레시피 1건을 처리해 {ingredient_id: {"sugar_g":..., "kcal":...}}를 반환한다.

    - ingredient_type='substituted'는 LLM 입력에서 제외한다(값을 채우지 않음).
    - 이미 채워진 common 재료는 재계산해 덮어쓰지 않고, 비어있던 것만 채운다.
    - 응답↔재료 매칭은 idx(입력 번호) 기준으로 1:1 하고, 실패분만 이름정규화/순서로
      폴백한다. 같은 이름 재료가 여러 개여도(예: "우유 100ml"/"우유 190ml") 값이
      섞이지 않는다.
    실패 시 예외를 그대로 올린다(호출측에서 잡아 실패 목록에 기록)."""
    try:
        steps = json.loads(recipe["steps"]) if recipe.get("steps") else []
    except (json.JSONDecodeError, TypeError):
        steps = []

    common_ingredients = [i for i in recipe_ingredients if i["ingredient_type"] == "common"]
    if not common_ingredients:
        return {}

    ing_payload = [
        {"name": i["name"], "amount": i["amount"], "ingredient_type": i["ingredient_type"]}
        for i in common_ingredients
    ]
    candidates_by_ingredient = {
        i["name"]: narrow_candidates(i["name"], raw_rows, limit=30) for i in common_ingredients
    }

    result = call_fill_llm(recipe["name"], steps, ing_payload, candidates_by_ingredient)

    out = {}
    used_result_pos = set()

    def take(ing, rr, pos):
        out[ing["id"]] = {"sugar_g": rr.get("sugar_g"), "kcal": rr.get("kcal")}
        used_result_pos.add(pos)

    def already_full(ing):
        return bool(ing.get("sugar_g", "").strip() and ing.get("kcal", "").strip())

    # (1) idx 매칭: common_ingredients[n-1] <-> 응답 idx=n
    matched_ids = set()
    for pos, rr in enumerate(result):
        try:
            n = int(rr.get("idx"))
        except (TypeError, ValueError):
            continue
        if 1 <= n <= len(common_ingredients):
            ing = common_ingredients[n - 1]
            if ing["id"] in matched_ids:
                continue
            if not already_full(ing):
                take(ing, rr, pos)
            matched_ids.add(ing["id"])

    unmatched = [
        i for i in common_ingredients
        if i["id"] not in matched_ids and not already_full(i)
    ]

    # (2) 이름 정규화 매칭(아직 안 쓴 응답만)
    if unmatched:
        for ing in list(unmatched):
            norm = _normalize_name(ing["name"])
            for pos, rr in enumerate(result):
                if pos in used_result_pos:
                    continue
                if _normalize_name(rr.get("name", "")) == norm:
                    take(ing, rr, pos)
                    unmatched.remove(ing)
                    break

    # (3) 순서 매칭(남은 것끼리)
    if unmatched:
        leftover = [rr for pos, rr in enumerate(result) if pos not in used_result_pos]
        for ing, rr in zip(unmatched, leftover):
            out[ing["id"]] = {"sugar_g": rr.get("sugar_g"), "kcal": rr.get("kcal")}

    return out


# ---------------------------------------------------------------------------
# CSV 입출력 / 완료 판정
# ---------------------------------------------------------------------------
def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def backup_file(path: Path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = path.parent / "backup" / ts
    backup_dir.mkdir(parents=True, exist_ok=True)
    dst = backup_dir / path.name
    shutil.copy2(path, dst)
    print(f"백업: {dst}")
    return dst


def write_ingredients_csv(path: Path, ingredients, filled):
    """현재까지의 filled 상태로 ingredients CSV 전체를 재작성한다.
    레시피 처리마다 호출해 중간에 중단돼도 결과가 보존되게 한다.
    입력 CSV에 추가 컬럼이 있어도 유지한다(INGREDIENTS_FIELDS 외 컬럼 보존)."""
    fieldnames = list(ingredients[0].keys()) if ingredients else INGREDIENTS_FIELDS
    for col in ("sugar_g", "kcal"):
        if col not in fieldnames:
            fieldnames.append(col)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for ing in ingredients:
            row = dict(ing)
            values = filled.get(ing["id"])
            if values is not None:
                row["sugar_g"] = "" if values.get("sugar_g") is None else values["sugar_g"]
                row["kcal"] = "" if values.get("kcal") is None else values["kcal"]
            writer.writerow(row)


def recipe_is_complete(recipe_ings) -> bool:
    """레시피의 common 재료가 전부(sugar_g와 kcal 둘 다) 채워졌으면 완료.
    common 재료가 하나도 없으면(전부 substituted) 채울 게 없으므로 완료로 간주."""
    common = [i for i in recipe_ings if i["ingredient_type"] == "common"]
    return all(i.get("sugar_g", "").strip() and i.get("kcal", "").strip() for i in common)


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def run(ingredients_csv: Path, recipes_csv: Path, raw_csv: Path,
        batch_size=None, max_workers=1):
    backup_file(ingredients_csv)

    raw_rows = load_csv(raw_csv)
    recipes = load_csv(recipes_csv)
    ingredients = load_csv(ingredients_csv)

    ingredients_by_recipe = defaultdict(list)
    for ing in ingredients:
        ingredients_by_recipe[ing["recipe_id"]].append(ing)

    # 기존 CSV에 이미 쓰여있는 값은 보존(sugar_g/kcal 중 하나라도 있으면).
    filled = {}
    for ing in ingredients:
        if ing.get("sugar_g", "").strip() or ing.get("kcal", "").strip():
            filled[ing["id"]] = {"sugar_g": ing["sugar_g"], "kcal": ing["kcal"]}

    # 재개: common 재료가 전부 채워진 레시피는 건너뛴다.
    pending_recipes = [
        r for r in recipes
        if ingredients_by_recipe.get(r["id"])
        and not recipe_is_complete(ingredients_by_recipe[r["id"]])
    ]

    if batch_size is not None:
        target = pending_recipes[:batch_size]
    else:
        target = pending_recipes

    done_count = len(recipes) - len(pending_recipes)
    print(f"완료 레시피 {done_count}건 스킵, 미처리 {len(pending_recipes)}건 중 "
          f"이번 실행 {len(target)}건 처리 (동시 {max_workers})")

    failed = []
    write_lock = threading.Lock()
    completed = 0
    total = len(target)

    def worker(recipe):
        rid = recipe["id"]
        return rid, recipe["name"], process_recipe(recipe, ingredients_by_recipe[rid], raw_rows)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, r): r for r in target}
        for future in as_completed(futures):
            recipe = futures[future]
            completed += 1
            try:
                rid, name, result = future.result()
                with write_lock:
                    filled.update(result)
                    write_ingredients_csv(ingredients_csv, ingredients, filled)
                print(f"[{completed}/{total}] recipe_id={rid} '{name[:30]}' 완료 "
                      f"(재료 {len(result)}개 채움)")
            except Exception as e:
                with write_lock:
                    failed.append(recipe["id"])
                print(f"[{completed}/{total}] recipe_id={recipe['id']} 실패: {e}")

    remaining = len(pending_recipes) - len(target)
    print(f"\n이번 실행 완료. 실패 {len(failed)}건, 남은 미처리 레시피 {remaining}건")
    if failed:
        print(f"실패 recipe_id: {failed}")


def main():
    parser = argparse.ArgumentParser(
        description="레시피 common 재료의 sugar_g/kcal을 Bedrock으로 채운다(substituted 제외)."
    )
    parser.add_argument("ingredients_csv", type=Path, help="recipe_ingredients CSV (이 파일이 수정됨)")
    parser.add_argument("recipes_csv", type=Path, help="recipes CSV (레시피명/steps 참조용, 읽기만)")
    parser.add_argument("raw_csv", type=Path, help="raw_ingredient_nutrients CSV (후보 조회용, 읽기만)")
    parser.add_argument("--batch", type=int, default=None,
                        help="이번 실행에 처리할 레시피 수(생략 시 남은 전부). 검증하며 나눠 돌릴 때 사용")
    parser.add_argument("--workers", type=int, default=1,
                        help="동시 처리 레시피 수(기본 1; 분당 5회 제한이라 크게 올려도 이득 적음)")
    args = parser.parse_args()

    for p in (args.ingredients_csv, args.recipes_csv, args.raw_csv):
        if not p.exists():
            parser.error(f"파일 없음: {p}")

    run(args.ingredients_csv, args.recipes_csv, args.raw_csv,
        batch_size=args.batch, max_workers=args.workers)


if __name__ == "__main__":
    main()
