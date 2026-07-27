import json, time
from pathlib import Path

# 자립: data_pipeline이 아니라 복사된 kafka/consumer/lib에서 import
from kafka.consumer.lib import fill_nutrition_all as nut_mod   # process_recipe (common 1건 영양)
from kafka.consumer.lib import match_ingredient_products as match_mod
from kafka.consumer.lib import fill_ingredient_nutrition as fillnut_mod
from kafka.consumer.lib import sum_recipe_nutrition as sum_mod
from kafka.consumer.lib import fill_recipe_base_nutrition as base_mod

from kafka.config import TOPIC_PARSED, TOPIC_DLQ, GROUP_MAIN
from kafka.common import kafka_client, db

MAX_RETRIES = 3

# 원재료 영양 DB는 consumer 시작 시 1회 로드해 재사용 (매 메시지마다 로드 금지)
# lib/로 함께 복사한 CSV를 쓴다(자립).
RAW_CSV_PATH = Path(__file__).resolve().parent / "lib" / "raw_ingredient_nutrients.csv"
_RAW_ROWS = None

def _raw_rows():
    global _RAW_ROWS
    if _RAW_ROWS is None:
        _RAW_ROWS = nut_mod.load_csv(RAW_CSV_PATH)
    return _RAW_ROWS


def insert_recipe(conn, msg: dict) -> "int | None":
    """recipes + recipe_ingredients 적재. 완전 중복(복합 UNIQUE 위반)이면 None.
    반환값이 int면 그 recipe_id로 common 영양을 바로 채운다(Step: fill_common)."""
    import psycopg
    steps_json = json.dumps(msg.get("steps", []), ensure_ascii=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO service.recipes
                    (video_id, name, thumbnail_url, steps, comparison_status,
                     published_at, source)
                VALUES (%s, %s, %s, %s, 'pending', %s, '유튜브')
                RETURNING id
                """,
                (msg["video_id"], msg["recipe_name"], msg.get("thumbnail_url"),
                 steps_json, msg.get("published_at") or None),
            )
            recipe_id = cur.fetchone()[0]
            for ing in msg.get("ingredients", []):
                cur.execute(
                    """
                    INSERT INTO service.recipe_ingredients
                        (recipe_id, name, amount, ingredient_type)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (recipe_id, ing.get("name", ""), ing.get("amount") or None,
                     ing.get("ingredient_type", "common")),
                )
        conn.commit()
        return recipe_id
    except psycopg.errors.UniqueViolation:
        conn.rollback()
        return None


def fill_common(conn, recipe_id: int, msg: dict) -> None:
    """common 재료 sugar_g/kcal를 process_recipe(1건 함수)로 채운다.
    process_recipe는 substituted를 자동 제외하므로 common만 채워진다.
    적재된 recipe_ingredients의 실제 id를 붙여 UPDATE한다."""
    # process_recipe 입력용으로 방금 적재된 재료(id 포함)를 조회
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, amount, ingredient_type, "
            "COALESCE(sugar_g::text,'') , COALESCE(kcal::text,'') "
            "FROM service.recipe_ingredients WHERE recipe_id = %s ORDER BY id",
            (recipe_id,),
        )
        rows = cur.fetchall()
    recipe = {"name": msg["recipe_name"], "steps": json.dumps(msg.get("steps", []), ensure_ascii=False)}
    recipe_ingredients = [
        {"id": r[0], "name": r[1], "amount": r[2] or "", "ingredient_type": r[3],
         "sugar_g": r[4], "kcal": r[5]}
        for r in rows
    ]
    result = nut_mod.process_recipe(recipe, recipe_ingredients, _raw_rows())  # {id: {sugar_g,kcal}}
    with conn.cursor() as cur:
        for ing_id, vals in result.items():
            cur.execute(
                "UPDATE service.recipe_ingredients SET sugar_g = %s, kcal = %s WHERE id = %s",
                (vals.get("sugar_g"), vals.get("kcal"), ing_id),
            )
    conn.commit()


def enrich_substituted(conn) -> None:
    """substituted 재료를 기존 검증 배치 함수로 계산(매칭→영양→합산→base).
    각 배치는 'WHERE ... IS NULL/NOT EXISTS'로 미완료분만 처리하므로 신규만 잡힌다.
    (consumer 병렬 시엔 서로의 신규 행을 건드릴 수 있음 — Global Constraints 참고.)"""
    import boto3, os
    bedrock = boto3.client("bedrock-runtime",
                           region_name=os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-2"))
    raw = match_mod.fetch_unmatched_ingredients(conn)
    if raw:
        missing = [n for _, n, c in raw if c is None]
        if missing:
            core_map = match_mod.extract_core_keywords(bedrock, missing)
            match_mod.save_core_keywords(conn, core_map, raw)
            raw = match_mod.fetch_unmatched_ingredients(conn)
        ings = [(rid, name, core or name) for rid, name, core in raw]
        match_mod.match_ingredients_to_products(conn, bedrock, ings)
    fillnut_mod.main()   # substituted 재료 영양 (자체 연결, 미완료분)
    sum_mod.main()       # 레시피 total 합산
    base_mod.main()      # base + 감소율 + comparison_status='ready'


def handle_message(msg: dict) -> None:
    conn = db.connect()
    try:
        recipe_id = insert_recipe(conn, msg)
        if recipe_id is None:
            print(f"중복 스킵: {msg['video_id']} / {msg['recipe_name']}")
            return
        fill_common(conn, recipe_id, msg)   # common 영양 (1건 함수)
        enrich_substituted(conn)            # substituted (배치, 미완료분)
        print(f"적재+계산 완료: recipe_id={recipe_id}")
    finally:
        conn.close()


def _to_dlq(producer, raw_value, err):
    producer.produce(TOPIC_DLQ, value=raw_value,
                     headers=[("error", str(err).encode("utf-8"))])
    producer.flush()


def run() -> None:
    consumer = kafka_client.make_consumer(GROUP_MAIN)
    dlq_producer = kafka_client.make_producer()
    consumer.subscribe([TOPIC_PARSED])
    try:
        while True:
            rec = consumer.poll(1.0)
            if rec is None:
                continue
            if rec.error():
                print(f"consumer error: {rec.error()}")
                continue
            raw = rec.value()
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    handle_message(json.loads(raw.decode("utf-8")))
                    consumer.commit(rec)   # 처리 성공 후에만 수동 커밋
                    break
                except Exception as e:
                    if attempt == MAX_RETRIES:
                        _to_dlq(dlq_producer, raw, e)
                        consumer.commit(rec)  # DLQ로 보냈으니 진행
                        print(f"DLQ 이동: {e}")
                    else:
                        time.sleep(2 ** attempt)
    finally:
        consumer.close()


if __name__ == "__main__":
    run()
