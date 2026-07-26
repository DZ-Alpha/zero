# -*- coding: utf-8 -*-
"""recipes.total_sugar_g / total_kcal 합산 배치.

레시피에 속한 recipe_ingredients(common+substituted 전부)의 sugar_g/kcal을 합산해
recipes.total_sugar_g/total_kcal을 채운다. 재료 중 하나라도 sugar_g가 NULL이면
(아직 계산 안 된 common 재료가 남아있다는 뜻) 그 레시피는 건너뛴다 - 불완전한
합산값이 채워지는 걸 막기 위함. total_sugar_g가 이미 채워진 레시피는 재계산하지
않는다(재계산하려면 이 스크립트를 다시 돌리기 전에 대상 레시피의 total_sugar_g를
먼저 NULL로 초기화해야 함).
"""
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

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


def fetch_ready_recipes(conn) -> list[tuple[int, str]]:
    """재료가 1개 이상이고, 모든 재료의 sugar_g가 채워져 있고, 아직 합산 안 된 레시피."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.id, r.name
            FROM service.recipes r
            JOIN service.recipe_ingredients ri ON ri.recipe_id = r.id
            WHERE r.total_sugar_g IS NULL
            GROUP BY r.id, r.name
            HAVING count(ri.id) = count(ri.id) FILTER (WHERE ri.sugar_g IS NOT NULL)
            ORDER BY r.id
            """
        )
        return cur.fetchall()


def sum_and_update(conn, recipe_id: int) -> tuple[float, float]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(sum(sugar_g), 0), COALESCE(sum(kcal), 0) "
            "FROM service.recipe_ingredients WHERE recipe_id = %s",
            (recipe_id,),
        )
        total_sugar, total_kcal = cur.fetchone()
        cur.execute(
            "UPDATE service.recipes SET total_sugar_g = %s, total_kcal = %s WHERE id = %s",
            (total_sugar, total_kcal, recipe_id),
        )
    return float(total_sugar), float(total_kcal)


def main():
    conn = psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    try:
        recipes = fetch_ready_recipes(conn)
        if not recipes:
            print("합산 대상 레시피가 없습니다 (모든 재료 계산 완료된 신규 레시피 없음).")
            return
        print(f"합산 대상 레시피 {len(recipes)}건 발견")

        for idx, (recipe_id, name) in enumerate(recipes, 1):
            total_sugar, total_kcal = sum_and_update(conn, recipe_id)
            conn.commit()
            print(f"[{idx}/{len(recipes)}] id={recipe_id} '{name}' -> "
                  f"sugar={total_sugar}g, kcal={total_kcal}")

        print(f"\n완료: {len(recipes)}건 합산")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
