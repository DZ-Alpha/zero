# -*- coding: utf-8 -*-
"""substituted 재료 <-> products 유사도 매칭 배치.

service.recipe_ingredients 중 아직 매칭 결과가 없는 ingredient_type='substituted'
재료를 찾아 Bedrock(Cohere Embed v4)으로 원문 임베딩을 계산하고, service.product_embeddings
(upsert_product_embeddings.py가 미리 채워 둔 벡터)와 코사인 유사도를 비교한다.
여기에 원문/core_keyword 부분문자열 매칭 보너스를 더한 하이브리드 점수로
score>=0.6인 상품만 service.recipe_ingredient_products에 저장한다.

core_keyword(재료명에서 브랜드/제품라인명을 뗀 핵심어, 예: "슈가프리 설탕"->"설탕")는
Nova Lite로 1회만 추출해 recipe_ingredients.core_keyword에 캐싱한다. 순수 벡터만으로는
브랜드/노이즈가 섞인 재료명(예: "슈가프리 설탕")의 매칭 품질이 떨어지고, 반대로
core_keyword만 단독으로 쓰면 "무가당 요플레"처럼 수식어가 실제로는 핵심 제약인 경우를
놓친다 - 원문 벡터를 유지하고 원문/core 중 더 잘 맞는 쪽의 키워드 보너스만 취하는 방식이
실측(100건 샘플)에서 두 실패 모드를 모두 피했다.

product_embeddings 자체의 upsert(신규/변경 상품 임베딩 계산)는 이 스크립트가 아니라
upsert_product_embeddings.py(상품 갱신 시에만 실행)가 담당한다. 이 스크립트는 이미
채워진 product_embeddings를 그대로 재사용만 한다.
"""
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import boto3
import json
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

EMBED_MODEL_ID = "global.cohere.embed-v4:0"
EMBED_DIMENSIONS = 1024  # product_embeddings.embedding 컬럼(VECTOR(1024))과 맞춤 (기본값은 1536)
CORE_KEYWORD_MODEL_ID = "apac.amazon.nova-lite-v1:0"
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")

MATCH_THRESHOLD = 0.6  # 100건 실측: 0.6 기준 80% 커버리지, 0.7은 대부분 미달 (docs 논의 참고)
TOP_N = 5  # 재료 1건당 최대 추천 상품 수

CORE_KEYWORD_PROMPT = """다음은 레시피에서 추출된 저당/저칼로리 대체 재료명 목록입니다.
상품 카탈로그 자체가 이미 저당/저칼로리/제로/무가당 상품만 모아둔 곳이므로,
재료명에서 "저당/무가당/제로/저칼로리/무설탕/라이트" 같은 이미 전제된 수식어는 제거하고
핵심 재료/카테고리명만 남기세요. 브랜드명이나 제품 라인명도 함께 제거하세요.
단, 상품 자체를 식별하는 데 필요한 고유명사(예: 알룰로스, 스테비아 같은 성분명)는 유지하세요.

JSON 배열로만 응답하세요: [{{"original": "원문", "core": "핵심어"}}, ...]

재료명 목록:
{items}
"""


def cohere_embed_batch(client, texts: list[str], input_type: str) -> list[list[float]]:
    out = []
    for i in range(0, len(texts), 96):
        batch = texts[i:i + 96]
        body = json.dumps({
            "texts": batch, "input_type": input_type, "embedding_types": ["float"],
            "output_dimension": EMBED_DIMENSIONS,
        })
        resp = client.invoke_model(
            modelId=EMBED_MODEL_ID, body=body,
            contentType="application/json", accept="application/json",
        )
        result = json.loads(resp["body"].read())
        out.extend(result["embeddings"]["float"])
    return out


def extract_core_keywords(client, names: list[str]) -> dict[str, str]:
    """재료명 -> 핵심어 매핑. Nova Lite로 최대 20건씩 배치 처리."""
    result_map = {}
    for i in range(0, len(names), 20):
        batch = names[i:i + 20]
        items_text = "\n".join(f"- {n}" for n in batch)
        prompt = CORE_KEYWORD_PROMPT.format(items=items_text)
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 2048},
        })
        resp = client.invoke_model(
            modelId=CORE_KEYWORD_MODEL_ID, body=body,
            contentType="application/json", accept="application/json",
        )
        result = json.loads(resp["body"].read())
        text = result["output"]["message"]["content"][0]["text"]
        match = re.search(r"\[.*\]", text, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else []
        for item in parsed:
            result_map[item["original"]] = item["core"]
    return result_map


def fetch_unmatched_ingredients(conn) -> list[tuple[int, str, str | None]]:
    """substituted 재료 중 recipe_ingredient_products에 아직 행이 없는 것만 조회."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ri.id, ri.name, ri.core_keyword
            FROM service.recipe_ingredients ri
            WHERE ri.ingredient_type = 'substituted'
              AND NOT EXISTS (
                  SELECT 1 FROM service.recipe_ingredient_products rip
                  WHERE rip.recipe_ingredient_id = ri.id
              )
            ORDER BY ri.id
            """
        )
        return cur.fetchall()


def save_core_keywords(conn, core_map: dict[str, str], ingredients: list[tuple[int, str, str | None]]) -> None:
    with conn.cursor() as cur:
        for ingredient_id, name, existing_core in ingredients:
            if existing_core is not None:
                continue
            core = core_map.get(name, name)
            cur.execute(
                "UPDATE service.recipe_ingredients SET core_keyword = %s WHERE id = %s",
                (core, ingredient_id),
            )
    conn.commit()


def keyword_bonus(text: str, product_name: str) -> float:
    if text in product_name:
        return 0.15
    for length in (4, 3, 2):
        for start in range(len(text) - length + 1):
            piece = text[start:start + length]
            if piece in product_name:
                return 0.10
    return 0.0


def find_similar_products(conn, ingredient_embedding: list[float], name: str, core: str, top_n: int) -> list[tuple[str, float]]:
    """product_embeddings와 코사인 유사도 비교 후, 원문/core 중 최대 키워드 보너스를 더한
    하이브리드 점수로 재정렬. 후보 풀은 벡터 유사도 상위로 넉넉히 가져온 뒤 재정렬한다."""
    vec_literal = "[" + ",".join(str(x) for x in ingredient_embedding) + "]"
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.product_id, p.product_name, 1 - (e.embedding <=> %s::vector) AS vec_score
            FROM service.product_embeddings e
            JOIN service.products p ON p.product_id = e.product_id
            ORDER BY e.embedding <=> %s::vector
            LIMIT %s
            """,
            (vec_literal, vec_literal, max(top_n * 5, 30)),
        )
        candidates = cur.fetchall()

    scored = []
    for product_id, product_name, vec_score in candidates:
        bonus = max(keyword_bonus(name, product_name), keyword_bonus(core, product_name))
        scored.append((product_id, vec_score + bonus))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


def save_matches(conn, recipe_ingredient_id: int, matches: list[tuple[str, float]]) -> int:
    """score>=0.6인 것만 저장. 최고 점수 1건만 is_primary=true."""
    qualified = [(pid, score) for pid, score in matches if score >= MATCH_THRESHOLD]
    if not qualified:
        return 0
    with conn.cursor() as cur:
        for i, (product_id, score) in enumerate(qualified):
            cur.execute(
                """
                INSERT INTO service.recipe_ingredient_products
                    (recipe_ingredient_id, product_id, match_score, is_primary)
                VALUES (%s, %s, %s, %s)
                """,
                (recipe_ingredient_id, product_id, score, i == 0),
            )
    return len(qualified)


def match_ingredients_to_products(conn, bedrock_client, ingredients: list[tuple[int, str, str]]) -> None:
    """입력을 받아 매칭 결과를 저장하는 순수 로직. 호출 시점(수동/cron/Kafka)과 무관하게 재사용."""
    total_saved = 0
    for idx, (ingredient_id, name, core) in enumerate(ingredients, 1):
        embedding = cohere_embed_batch(bedrock_client, [name], "search_query")[0]
        matches = find_similar_products(conn, embedding, name, core, TOP_N)
        saved = save_matches(conn, ingredient_id, matches)
        conn.commit()
        total_saved += saved
        status = f"{saved}건 매칭" if saved else f"매칭 상품 없음({MATCH_THRESHOLD} 미만)"
        print(f"[{idx}/{len(ingredients)}] id={ingredient_id} '{name}' -> {status}")
    print(f"\n완료: 재료 {len(ingredients)}건 처리, 매칭 행 {total_saved}건 저장")


def main():
    conn = psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    try:
        raw_ingredients = fetch_unmatched_ingredients(conn)
        if not raw_ingredients:
            print("매칭 대상 신규 substituted 재료가 없습니다.")
            return
        print(f"매칭 대상 substituted 재료 {len(raw_ingredients)}건 발견")

        missing_core = [name for _, name, core in raw_ingredients if core is None]
        if missing_core:
            print(f"core_keyword 미보유 {len(missing_core)}건, Nova Lite로 추출 중...")
            core_map = extract_core_keywords(bedrock_client, missing_core)
            save_core_keywords(conn, core_map, raw_ingredients)
            raw_ingredients = fetch_unmatched_ingredients(conn)  # core_keyword 반영된 최신 상태 재조회

        ingredients = [(rid, name, core or name) for rid, name, core in raw_ingredients]
        match_ingredients_to_products(conn, bedrock_client, ingredients)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
