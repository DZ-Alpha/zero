# -*- coding: utf-8 -*-
"""recipes.base_sugar_g / base_kcal 및 감소율 계산 배치.

레시피 전체를 LLM에게 다시 추정시키면 이미 확정된 total_sugar_g/kcal(재료별
실측 합산)보다 base가 더 낮게 나오는 논리적 역전이 생길 수 있다(실측 확인:
"다이어트김치" 사례 - substituted 22.2g인데 레시피 전체를 다시 추정하니
12g으로 나옴). 이를 구조적으로 막기 위해, LLM에게는 레시피 전체가 아니라
substituted 재료 각각만 "대체 전 원래 재료였다면 당/칼로리가 얼마인지" 묻고
recipe_ingredients.base_sugar_g/base_kcal에 저장한다. common 재료는 대체품이
아니므로 sugar_g/kcal 값을 base_sugar_g/base_kcal에 그대로 복사한다(자기 자신이
곧 base). recipes.base_sugar_g/base_kcal은 이렇게 재료 단위로 확정된 값들을
코드가 합산한 결과이므로, base >= total이 재료 단위에서 구조적으로 보장된다
(대체재가 원본보다 저당/저칼로리라는 전제가 개별 재료 단위에서 깨지지 않는 한).

base_sugar_g/base_kcal이 채워지면 sugar_reduction_pct/kcal_reduction_pct를
코드로 직접 계산하고, total_sugar_g/total_kcal/base_sugar_g/base_kcal 4개가
모두 채워진 레시피는 comparison_status를 'ready'로 갱신한다.
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

LLM_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")

BASE_INGREDIENT_PROMPT = """다음은 레시피에 쓰인 저당/저칼로리/제로 대체 재료와
정량입니다. 각 재료가 대체 재료가 아닌 일반적인 원래 재료(예: 알룰로스/스테비아
->설탕, 무가당 요플레->일반 요플레, 곤약면->일반 면)였다면, 동일한 정량 기준으로
당류(g)와 열량(kcal)이 얼마일지 추정하세요.

순수 JSON 배열로만 응답하세요. 주석이나 설명 문구를 절대 추가하지 마세요:
[{{"id": 재료ID, "sugar_g": 숫자, "kcal": 숫자}}, ...]

재료 목록 (형식: ID | 재료명 | 원문 정량):
{items}
"""


def call_llm_batch(client, rows: list[tuple[int, str, str]], batch_size: int = 20) -> dict[int, dict]:
    result_map = {}
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        items_text = "\n".join(f"{rid} | {name} | {amount}" for rid, name, amount in batch)
        prompt = BASE_INGREDIENT_PROMPT.format(items=items_text)
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        })
        resp = client.invoke_model(modelId=LLM_MODEL_ID, body=body,
                                    contentType="application/json", accept="application/json")
        result = json.loads(resp["body"].read())
        text = "".join(b["text"] for b in result["content"] if b.get("type") == "text")
        match = re.search(r"\[.*\]", text, re.DOTALL)
        raw_json = match.group(0) if match else "[]"
        raw_json = re.sub(r"//[^\n]*", "", raw_json)
        raw_json = re.sub(r"/\*.*?\*/", "", raw_json, flags=re.DOTALL)
        parsed = json.loads(raw_json)
        # LLM이 응답에 적는 "id"는 신뢰하지 않고 입력 batch 순서로 매핑(값 뒤섞임 방지).
        if len(parsed) != len(batch):
            print(f"  [경고] LLM 응답 {len(parsed)}건 != 입력 {len(batch)}건 — 순서 매핑")
        for pos, item in enumerate(parsed):
            if pos >= len(batch):
                break
            result_map[int(batch[pos][0])] = item
    return result_map


def fetch_unbased_substituted(conn) -> list[tuple[int, str, str]]:
    """base_sugar_g가 아직 없는 substituted 재료 (sugar_g가 채워진 것만 대상)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, amount FROM service.recipe_ingredients
            WHERE ingredient_type = 'substituted'
              AND sugar_g IS NOT NULL
              AND base_sugar_g IS NULL
            ORDER BY id
            """
        )
        return cur.fetchall()


def copy_common_base(conn) -> int:
    """common 재료는 그 자체가 base이므로 sugar_g/kcal을 base_sugar_g/base_kcal에 복사."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE service.recipe_ingredients
            SET base_sugar_g = sugar_g, base_kcal = kcal
            WHERE ingredient_type = 'common'
              AND sugar_g IS NOT NULL
              AND base_sugar_g IS NULL
            """
        )
        updated = cur.rowcount
    conn.commit()
    return updated


def save_ingredient_base(conn, ingredient_id: int, base_sugar_g: float, base_kcal: float) -> None:
    # base는 "대체 전 원래 재료"의 당/칼로리이므로 개념상 항상 현재값(sugar_g/kcal)
    # 이상이어야 한다. 하지만 아몬드가루처럼 원래부터 저당인 재료는 LLM이 base를
    # 현재값보다 낮게 추정해 sugar_reduction_pct가 음수로 역전된다(실측: 아몬드가루
    # 140g 당 42.22g인데 base 5.6g). GREATEST로 현재 컬럼값 이상을 보장해 역전을
    # 구조적으로 막는다(감소율 하한 0%). 정량 미해석 등으로 sugar_g가 NULL이면
    # COALESCE로 추정값을 그대로 쓴다.
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE service.recipe_ingredients
            SET base_sugar_g = GREATEST(%s, COALESCE(sugar_g, %s)),
                base_kcal = GREATEST(%s, COALESCE(kcal, %s))
            WHERE id = %s
            """,
            (round(base_sugar_g, 2), round(base_sugar_g, 2),
             round(base_kcal, 2), round(base_kcal, 2), ingredient_id),
        )
    conn.commit()


def sum_recipe_base(conn) -> int:
    """재료 전체(common+substituted)의 base_sugar_g/base_kcal이 다 채워진 레시피만
    recipes.base_sugar_g/base_kcal을 합산해 채운다."""
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH ready AS (
                SELECT ri.recipe_id
                FROM service.recipe_ingredients ri
                GROUP BY ri.recipe_id
                HAVING count(ri.id) = count(ri.id) FILTER (WHERE ri.base_sugar_g IS NOT NULL)
            ),
            totals AS (
                SELECT recipe_id, sum(base_sugar_g) AS base_sugar_g, sum(base_kcal) AS base_kcal
                FROM service.recipe_ingredients
                WHERE recipe_id IN (SELECT recipe_id FROM ready)
                GROUP BY recipe_id
            )
            UPDATE service.recipes r
            SET base_sugar_g = t.base_sugar_g, base_kcal = t.base_kcal
            FROM totals t
            WHERE r.id = t.recipe_id AND r.base_sugar_g IS NULL
            """
        )
        updated = cur.rowcount
    conn.commit()
    return updated


def update_reduction_and_status(conn) -> int:
    """감소율 계산 + comparison_status='ready' 갱신. base가 0인 경우(원본조차
    무당) 0으로 나누기를 피해 감소율을 0으로 둔다.

    ⚠️ sugar_reduction_pct/kcal_reduction_pct는 NUMERIC(5,2)라 절대값 999.99가 상한.
    정량 오해석 등으로 total이 base보다 크게 튀면 감소율이 -1000%+가 되어 오버플로우로
    UPDATE 전체가 크래시하고, 그러면 consumer가 죽어 뒤 메시지까지 막힌다. 이를 막기 위해
    GREATEST/LEAST로 [-999.99, 999.99] 범위로 clamp한다(데이터 보존 + 크래시 방지)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE service.recipes
            SET sugar_reduction_pct = CASE
                    WHEN base_sugar_g > 0 THEN
                        GREATEST(-999.99, LEAST(999.99,
                            ROUND((base_sugar_g - total_sugar_g) / base_sugar_g * 100, 2)))
                    ELSE 0
                END,
                kcal_reduction_pct = CASE
                    WHEN base_kcal > 0 THEN
                        GREATEST(-999.99, LEAST(999.99,
                            ROUND((base_kcal - total_kcal) / base_kcal * 100, 2)))
                    ELSE 0
                END,
                comparison_status = 'ready'
            WHERE total_sugar_g IS NOT NULL AND total_kcal IS NOT NULL
              AND base_sugar_g IS NOT NULL AND base_kcal IS NOT NULL
              AND comparison_status IS DISTINCT FROM 'ready'
            """
        )
        updated = cur.rowcount
    conn.commit()
    return updated


def main():
    conn = psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    try:
        common_updated = copy_common_base(conn)
        print(f"common 재료 base 복사: {common_updated}건")

        substituted = fetch_unbased_substituted(conn)
        if substituted:
            print(f"\nsubstituted 재료 base 추정 대상 {len(substituted)}건 처리 중...")
            base_map = call_llm_batch(bedrock_client, substituted)
            saved = 0
            for rid, name, amount in substituted:
                base = base_map.get(rid)
                if not base:
                    print(f"  [경고] id={rid} '{name}' base 추정 실패, 건너뜀")
                    continue
                save_ingredient_base(conn, rid, base["sugar_g"], base["kcal"])
                saved += 1
            print(f"  -> {saved}건 저장")
        else:
            print("\nsubstituted 재료 base 추정 대상 없음")

        recipe_updated = sum_recipe_base(conn)
        print(f"\nrecipes.base_sugar_g/base_kcal 합산: {recipe_updated}건")

        status_updated = update_reduction_and_status(conn)
        print(f"감소율 계산 및 comparison_status='ready' 갱신: {status_updated}건")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
