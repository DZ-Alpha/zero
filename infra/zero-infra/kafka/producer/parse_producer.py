import json, sys

from kafka.config import TOPIC_PARSED
from kafka.common import redis_cursor, kafka_client, db
from kafka.producer import discover_extract as ex   # 자립 복사 모듈 (data_pipeline import 없음)


def already_in_db(conn, video_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM service.recipes WHERE video_id = %s LIMIT 1", (video_id,))
        return cur.fetchone() is not None


def build_message(video_id: str, published_at: str, recipe: dict) -> dict:
    return {
        "video_id": video_id,
        "recipe_name": recipe.get("recipe_name") or "",
        "published_at": published_at or "",
        "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        "steps": recipe.get("steps", []),
        "ingredients": recipe.get("ingredients", []),
    }


def _sanitize_ingredients(ingredients: list) -> list:
    for ing in ingredients:
        if ing.get("ingredient_type") not in ("substituted", "common"):
            ing["ingredient_type"] = "common"
    return ingredients


def run(limit: int = 200) -> None:
    since = redis_cursor.read_cursor()
    candidates, fetched_at = ex.discover_since_cursor(limit, since=since)
    producer = kafka_client.make_producer()
    conn = db.connect()
    published = 0
    try:
        for cand in candidates:
            vid = cand["video_id"]
            if already_in_db(conn, vid):
                continue
            description, comments = ex.fetch_description_and_comments(vid, max_comments=8)
            user_text = ex.build_user_text(cand["title"], description, comments)
            parsed = ex.parse_json_response(ex.call_llm(user_text))
            for recipe in parsed.get("recipes", []):
                if not recipe.get("is_complete"):
                    continue
                ingredients = _sanitize_ingredients(recipe.get("ingredients", []))
                ok, _ = ex.passes_quality_gate(recipe.get("steps", []), ingredients)
                if not ok:
                    continue
                recipe["ingredients"] = ingredients
                msg = build_message(vid, cand.get("published_at", ""), recipe)
                producer.produce(TOPIC_PARSED, key=vid,
                                 value=json.dumps(msg, ensure_ascii=False).encode("utf-8"))
                published += 1
        producer.flush()
    finally:
        conn.close()
    redis_cursor.write_cursor(fetched_at)   # 발행 완료 후에만 커서 갱신 (유실 방지)
    print(f"발행 완료: {published}건, 커서 갱신: {fetched_at.isoformat()}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    run(n)
