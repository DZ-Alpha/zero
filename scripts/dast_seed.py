#!/usr/bin/env python3
"""
DAST staging PG 목데이터 시더 (재현 가능).

무엇: DAST active scan용 가짜 데이터를 staging PG에 삽입한다. 실PII 0 (전부 Faker).
왜: 격리된 staging PG는 스키마(구조)만 있고 데이터가 비어 있다. IDOR/주입 스캔이
    표면을 밟으려면 유저·건강정보·식단·모임 멤버십이 있어야 한다.

방식: 모델 import 없이 SQLAlchemy Core로 직접 INSERT한다(마이크로서비스라 서비스별
    Base가 달라 한 프로세스에서 모델을 섞으면 충돌 → raw INSERT가 안전).
    소유 테이블만 채우면 _ref는 같은 물리 테이블이라 자동 반영(따로 안 채움).

재현성: 이 스크립트를 git에 보관. staging PG 재생성 시 스키마 동기화
    (scripts/dast-stg-schema-sync.sh) 후 이 시더를 재실행하면 목데이터 복원.
    Faker seed 고정으로 매 실행 동일 데이터.

멱등: 시작 시 대상 테이블을 TRUNCATE(격리 DB 전용이라 안전) 후 재삽입.

접속: 환경변수 PG_DSN (예: postgresql+psycopg://yesman:PW@dang-stg-pg-rw...:5432/zero).
    미설정 시 POSTGRES_* 개별 변수로 조립.

실행: staging PG에 도달 가능한 곳에서. (임시 파이썬 파드 또는 서비스 파드 exec)
    pip install sqlalchemy psycopg faker
    PG_DSN=... python scripts/dast_seed.py

FK 삽입 순서: users → tags → user_health_profiles → meal_logs → rooms → room_members
IDOR 구성: 유저 A(멤버)/B(비멤버) 쌍 — A 토큰으로 B 리소스 접근 시도 검증용.
"""
import os
import uuid
from datetime import datetime, timezone

from faker import Faker
from sqlalchemy import create_engine, text

# --- 규모 (Task0 확정: 소규모) ---
N_USERS = 20
MEALS_PER_USER = 4       # 유저당 식단 3~5 → 고정 4
N_ROOMS = 5

fake = Faker("ko_KR")
Faker.seed(20260730)     # 재현성: 매 실행 동일 데이터


def dsn() -> str:
    if os.getenv("PG_DSN"):
        return os.environ["PG_DSN"]
    user = os.getenv("POSTGRES_USER", "yesman")
    pw = os.environ["POSTGRES_PASSWORD"]          # 필수 — 하드코딩 금지
    host = os.getenv("POSTGRES_HOST", "dang-stg-pg-rw.dang-be-ns-stg.svc.cluster.local")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "zero")
    return f"postgresql+psycopg://{user}:{pw}@{host}:{port}/{db}"


def guard_not_prod(conn) -> None:
    """격리 가드: 운영 DB엔 절대 시딩하지 않는다. 실데이터가 있으면 중단."""
    # 운영 users엔 실유저가 많다. staging은 비어 있어야 정상.
    # 이미 시딩된 재실행은 정확히 N_USERS개 dast 유저라 통과.
    n = conn.execute(text(
        "SELECT count(*) FROM users WHERE email NOT LIKE '%@dast.local'"
    )).scalar_one()
    if n > 0:
        raise SystemExit(
            f"중단: users에 dast 계정이 아닌 행이 {n}개 있음. 운영 DB로 의심되어 시딩 거부."
        )


def seed() -> None:
    engine = create_engine(dsn(), future=True)
    with engine.begin() as conn:
        guard_not_prod(conn)

        # 멱등: 대상 테이블 비우기(격리 DB 전용이라 안전). FK 역순 truncate + CASCADE.
        conn.execute(text(
            "TRUNCATE community.room_members, community.rooms, service.meal_logs, "
            "service.user_health_profiles, service.tags, users "
            "RESTART IDENTITY CASCADE"
        ))

        # 1) users — id는 SERIAL(auto). RETURNING으로 실제 id 수집.
        user_ids: list[int] = []
        for i in range(N_USERS):
            uid = conn.execute(text(
                "INSERT INTO users (email, display_name, optional_agree, created_at, updated_at) "
                "VALUES (:email, :dn, false, now(), now()) RETURNING id"
            ), {"email": f"user{i}@dast.local", "dn": fake.user_name()}).scalar_one()
            user_ids.append(uid)

        # 2) service.tags — tag_type/code/name NOT NULL.
        tag_types = ["CATEGORY", "ALLERGEN", "SWEETENER", "HEALTH_LABEL"]
        for i, tt in enumerate(tag_types):
            conn.execute(text(
                "INSERT INTO service.tags (tag_id, tag_type, tag_code, tag_name, active) "
                "VALUES (:id, :tt, :code, :name, true)"
            ), {"id": uuid.uuid4(), "tt": tt, "code": f"{tt}_{i}", "name": fake.word()})

        # 3) service.user_health_profiles — user_id PK(→users). 개인 건강정보(IDOR 핵심).
        for uid in user_ids:
            conn.execute(text(
                "INSERT INTO service.user_health_profiles "
                "(user_id, birth_year, gender, height_cm, weight_kg, daily_sugar_target_g) "
                "VALUES (:uid, :by, :g, :h, :w, :sugar)"
            ), {
                "uid": uid,
                "by": fake.random_int(1970, 2005),
                "g": fake.random_element(["M", "F"]),
                "h": fake.random_int(150, 190),
                "w": fake.random_int(45, 95),
                "sugar": 50,
            })

        # 4) service.meal_logs — user_id(→users), eaten_at NOT NULL.
        for uid in user_ids:
            for _ in range(MEALS_PER_USER):
                conn.execute(text(
                    "INSERT INTO service.meal_logs "
                    "(meal_log_id, user_id, input_type, meal_type, analysis_status, "
                    " needs_user_confirmation, eaten_at, created_at) "
                    "VALUES (:id, :uid, 'MANUAL', :mt, 'DONE', false, now(), now())"
                ), {
                    "id": uuid.uuid4(),
                    "uid": uid,
                    "mt": fake.random_element(["BREAKFAST", "LUNCH", "DINNER", "SNACK"]),
                })

        # 5) community.rooms — owner_id(→users).
        room_ids: list[uuid.UUID] = []
        for i in range(N_ROOMS):
            rid = uuid.uuid4()
            conn.execute(text(
                "INSERT INTO community.rooms (id, name, emoji, owner_id, ranking_opt_in) "
                "VALUES (:id, :name, :emoji, :owner, true)"
            ), {"id": rid, "name": fake.word()[:24], "emoji": "🥗", "owner": user_ids[i % N_USERS]})
            room_ids.append(rid)

        # 6) community.room_members — IDOR 쌍 구성:
        #    방마다 멤버를 다르게 넣어, 각 방에 "멤버 유저"와 "비멤버 유저"가 공존하게 한다.
        #    → 스캔 시 비멤버 토큰으로 방 접근 시도(접근제어 검증).
        for i, rid in enumerate(room_ids):
            # 방 i의 멤버 = user_ids[i], user_ids[i+1] (owner 포함). 나머지는 비멤버.
            members = {user_ids[i % N_USERS], user_ids[(i + 1) % N_USERS]}
            for uid in members:
                role = "owner" if uid == user_ids[i % N_USERS] else "member"
                conn.execute(text(
                    "INSERT INTO community.room_members (room_id, user_id, role) "
                    "VALUES (:rid, :uid, :role) ON CONFLICT DO NOTHING"
                ), {"rid": rid, "uid": uid, "role": role})

    print(f"시딩 완료: users={N_USERS}, health_profiles={N_USERS}, "
          f"meal_logs={N_USERS * MEALS_PER_USER}, rooms={N_ROOMS}, tags=4")
    print(f"IDOR 쌍 예시: user_id={user_ids[0]}(방0 멤버) vs user_id={user_ids[3]}(방0 비멤버)")


if __name__ == "__main__":
    seed()
