# -*- coding: utf-8 -*-
"""substituted 재료의 sugar_g/kcal 채우기 배치.

recipe_ingredient_products(재료<->상품 매칭)를 활용해 service.recipe_ingredients의
sugar_g/kcal을 채운다. 재료 3가지 경우로 나뉜다:

1. amount가 계량 불가 표현("취향껏" 등) -> sugar_g=0, kcal=0 (소량 조미료로 간주,
   recipes.total_sugar_g 합산 시 0으로 더해짐)
2. 매칭 상품이 있는 재료 -> LLM(Nova Lite)으로 원문 amount를 g/ml로 환산한 뒤,
   is_primary=true 매칭 상품의 영양성분(기준량 대비)을 환산량 비율로 코드가 직접 계산
3. 매칭 상품이 없는 재료(52건, 2026-07-17 기준) -> LLM에게 재료명+원문 amount를 그대로 주고
   당류(g)/열량(kcal)을 직접 추정하게 함 (참고할 상품 데이터가 없으므로 단위환산과
   영양계산을 분리하지 않고 한 번에 요청)
"""
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import boto3
import psycopg
from dotenv import load_dotenv

# 표준 조리단위(t=5, T=15, g/kg/ml/L)는 LLM이 아니라 코드로 확정 환산한다.
# (Nova Lite가 "1t"를 0.5~1000으로 불안정 환산하는 버그 대응 — common과 동일 방식)
try:
    from kafka.consumer.lib.unit_converter import parse_standard_unit
except ImportError:  # 원본 data_pipeline에서 직접 실행 시
    from nutrition_fill.unit_converter import parse_standard_unit

sys.stdout.reconfigure(errors="replace")

ROOT = Path(__file__).parent
# .env 상위탐색(로컬 zero_data/·서버 opt/zero-infra/ 모두 대응, 자립)
for _p in [Path(__file__).resolve(), *Path(__file__).resolve().parents][:7]:
    if (_p / ".env").is_file():
        load_dotenv(_p / ".env", override=False)
        break

_db_url = urlparse(os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://"))
DB_HOST = _db_url.hostname
DB_PORT = _db_url.port
DB_NAME = _db_url.path.lstrip("/")
DB_USER = _db_url.username
DB_PASSWORD = unquote(_db_url.password)

LLM_MODEL_ID = "apac.amazon.nova-lite-v1:0"
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")

NO_AMOUNT_PATTERNS = ("취향껏", "기호에 맞게", "기호에", "적당량", "생략")

UNIT_CONVERT_PROMPT = """다음은 레시피 재료명과 원문 정량 표기, 그리고 그 재료와 매칭된
상품의 영양성분 기준 단위입니다. 각 재료의 정량을 반드시 지정된 기준 단위(target_unit)로
환산하세요.

환산 규칙(반드시 지킬 것):
- 이미 g/ml 단위면 그 숫자를 그대로 사용하세요(예: "50g"이면 50, 절대 100으로 반올림 금지).
- 표준 조리단위는 정확히 환산: **T(큰술/스푼)=15, t(작은술/티스푼)=5**, 1컵=200,
  1개=재료별 통상 무게. "1T"는 15, "1t"는 5입니다(1000 같은 큰 값이 절대 아님).
- "50~60g"처럼 범위면 중앙값(55). "300g / 1모"처럼 병기면 g/ml 쪽 우선.
- "반스푼"=T의 절반=7.5, "1/3팩"은 그 재료 1팩 통상 용량의 1/3.
- "약간"≈0.5, "적당량"≈5, "취향껏"≈5 등 모호 단위는 재료 종류·문맥으로 합리적 추정.
- target_unit이 ml인데 고체면 밀도를, g인데 액체면 1ml≈1g으로 환산.
- 결과 숫자는 상식적 범위여야 함(양념 1스푼이 수백 g일 수 없음).

순수 JSON 배열로만 응답하세요. 주석(//, /* */)이나 설명 문구를 절대 추가하지 마세요:
[{{"id": 재료ID, "value": 숫자}}, ...]

재료 목록 (형식: ID | 재료명 | 원문 정량 | target_unit):
{items}
"""

DIRECT_NUTRITION_PROMPT = """다음은 상품 카탈로그에 마땅한 매칭 상품이 없는
저당/저칼로리 대체 재료명과 정량입니다. 이 재료를 이 정량만큼 섭취했을 때의
당류(g)와 열량(kcal)을 일반적인 영양 정보를 근거로 추정하세요.

순수 JSON 배열로만 응답하세요. 주석(//, /* */)이나 설명 문구를 절대 추가하지 마세요:
[{{"id": 재료ID, "sugar_g": 숫자, "kcal": 숫자}}, ...]

재료 목록 (형식: ID | 재료명 | 원문 정량):
{items}
"""


def call_llm_batch(client, prompt_template: str, rows: list[tuple], batch_size: int = 20) -> dict[int, dict]:
    """rows: (id, name, amount) 또는 (id, name, amount, target_unit). 응답을 {id: {...}} 형태로 병합.

    ⚠️ LLM이 응답에 적어 보내는 "id"는 신뢰하지 않는다(큰 배치에서 값이 뒤섞여 엉뚱한
    재료에 잘못된 환산값이 붙는 버그가 실측됨 — 예: "1t"가 1000g으로). 대신 **입력 batch
    순서**를 진실의 원천으로 삼아, 응답 배열의 n번째를 입력 batch의 n번째 재료(rows의 실제
    id)에 대응시킨다. common(fill_nutrition_all)의 idx 매칭과 같은 원리."""
    result_map = {}
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        items_text = "\n".join(" | ".join(str(v) for v in row) for row in batch)
        prompt = prompt_template.format(items=items_text)
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 2048},
        })
        resp = client.invoke_model(modelId=LLM_MODEL_ID, body=body,
                                    contentType="application/json", accept="application/json")
        result = json.loads(resp["body"].read())
        text = result["output"]["message"]["content"][0]["text"]
        match = re.search(r"\[.*\]", text, re.DOTALL)
        raw_json = match.group(0) if match else "[]"
        # 프롬프트로 금지해도 모델이 이따금 //, /* */ 주석을 섞어 응답하므로 방어적으로 제거
        raw_json = re.sub(r"//[^\n]*", "", raw_json)
        raw_json = re.sub(r"/\*.*?\*/", "", raw_json, flags=re.DOTALL)
        parsed = json.loads(raw_json)
        if len(parsed) != len(batch):
            print(f"  [경고] LLM 응답 {len(parsed)}건 != 입력 {len(batch)}건 — "
                  f"id 대신 순서로 매핑하되 개수 불일치는 뒤쪽이 누락될 수 있음")
        # 입력 batch 순서로 매핑(LLM id 불신). rows의 첫 요소가 실제 DB id.
        for pos, item in enumerate(parsed):
            if pos >= len(batch):
                break
            real_id = int(batch[pos][0])
            result_map[real_id] = item
    return result_map


def fetch_no_amount_ingredients(conn) -> list[int]:
    """계량 불가 표현인 substituted 재료 id 목록."""
    pattern = "|".join(NO_AMOUNT_PATTERNS)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id FROM service.recipe_ingredients
            WHERE ingredient_type = 'substituted'
              AND sugar_g IS NULL
              AND amount ~ %s
            """,
            (pattern,),
        )
        return [r[0] for r in cur.fetchall()]


def fetch_matched_ingredients(conn) -> list[tuple[int, str, str, str, float, str, float, float]]:
    """매칭 상품(is_primary=true)이 있고 아직 sugar_g가 안 채워진 재료.
    반환: (ingredient_id, name, amount, product_name, serving_value, serving_unit, sugars, calories)"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ri.id, ri.name, ri.amount,
                   p.product_name, p.serving_value, p.serving_unit, p.sugars, p.calories
            FROM service.recipe_ingredients ri
            JOIN service.recipe_ingredient_products rip
                ON rip.recipe_ingredient_id = ri.id AND rip.is_primary = true
            JOIN service.products p ON p.product_id = rip.product_id
            WHERE ri.ingredient_type = 'substituted'
              AND ri.sugar_g IS NULL
            ORDER BY ri.id
            """
        )
        return cur.fetchall()


def fetch_unmatched_ingredients(conn) -> list[tuple[int, str, str]]:
    """매칭 상품이 없고 아직 sugar_g가 안 채워진 substituted 재료.
    반환: (ingredient_id, name, amount)"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ri.id, ri.name, ri.amount
            FROM service.recipe_ingredients ri
            WHERE ri.ingredient_type = 'substituted'
              AND ri.sugar_g IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM service.recipe_ingredient_products rip
                  WHERE rip.recipe_ingredient_id = ri.id
              )
            ORDER BY ri.id
            """
        )
        return cur.fetchall()


def set_zero(conn, ids: list[int]) -> None:
    if not ids:
        return
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE service.recipe_ingredients SET sugar_g = 0, kcal = 0 WHERE id = ANY(%s)",
            (ids,),
        )
    conn.commit()


def update_nutrition(conn, ingredient_id: int, sugar_g: float, kcal: float) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE service.recipe_ingredients SET sugar_g = %s, kcal = %s WHERE id = %s",
            (round(sugar_g, 2), round(kcal, 2), ingredient_id),
        )
    conn.commit()


def calc_from_product(converted_value: float, serving_value: float, sugars: float, calories: float) -> tuple[float, float]:
    """환산된 재료 정량(g/ml) 대비 상품 기준량으로 비례 계산."""
    ratio = converted_value / float(serving_value)
    return float(sugars) * ratio, float(calories) * ratio


def main():
    conn = psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    try:
        # 1. 계량 불가 -> 0/0
        zero_ids = fetch_no_amount_ingredients(conn)
        if zero_ids:
            print(f"계량 불가 표현 {len(zero_ids)}건 -> sugar_g=0, kcal=0")
            set_zero(conn, zero_ids)

        # 2. 매칭 상품 있는 재료: 단위환산 + 영양계산(코드)
        #    표준단위(t/T/g/kg/ml/L)는 parse_standard_unit(코드)로 확정 환산하고,
        #    실패한(모호한: "적당량","1개" 등) 것만 LLM으로 환산한다.
        matched = fetch_matched_ingredients(conn)
        if matched:
            print(f"\n매칭 상품 있는 재료 {len(matched)}건 처리 중...")
            unit_map = {}
            llm_rows = []
            for rid, name, amount, product_name, serving_value, serving_unit, sugars, calories in matched:
                target = "ml" if serving_unit.lower() == "ml" else "g"
                std = parse_standard_unit(amount)  # (수치, "g"|"ml") 또는 None
                if std is not None:
                    unit_map[rid] = {"id": rid, "value": std[0]}  # 코드 확정 환산
                else:
                    llm_rows.append((rid, name, amount, target))  # 모호 → LLM
            if llm_rows:
                unit_map.update(call_llm_batch(bedrock_client, UNIT_CONVERT_PROMPT, llm_rows))

            saved = 0
            for rid, name, amount, product_name, serving_value, serving_unit, sugars, calories in matched:
                conv = unit_map.get(rid)
                if not conv:
                    print(f"  [경고] id={rid} '{name}' 단위환산 실패, 건너뜀")
                    continue
                sugar_g, kcal = calc_from_product(conv["value"], serving_value, sugars, calories)
                update_nutrition(conn, rid, sugar_g, kcal)
                saved += 1
            print(f"  -> {saved}건 저장")

        # 3. 매칭 상품 없는 재료: LLM 통합 추정
        unmatched = fetch_unmatched_ingredients(conn)
        if unmatched:
            print(f"\n매칭 상품 없는 재료 {len(unmatched)}건 처리 중 (LLM 직접 추정)...")
            nutrition_map = call_llm_batch(bedrock_client, DIRECT_NUTRITION_PROMPT, unmatched)

            saved = 0
            for rid, name, amount in unmatched:
                nut = nutrition_map.get(rid)
                if not nut:
                    print(f"  [경고] id={rid} '{name}' 추정 실패, 건너뜀")
                    continue
                update_nutrition(conn, rid, nut["sugar_g"], nut["kcal"])
                saved += 1
            print(f"  -> {saved}건 저장")

        print("\n완료.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
