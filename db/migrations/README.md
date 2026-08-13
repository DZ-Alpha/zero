# 기동 시 DDL과 RDS 이전 (DB_AUTO_MIGRATE)

2026-08-13 전수 감사 C-1 대응.

## 지금 무슨 일이 일어나는가

백엔드 7개 서비스가 **기동 시점에 DDL을 직접 실행**한다. 온프렘에서는 앱 role에
DDL 권한이 있어 동작하지만, RDS에서 최소권한 app role을 쓰면
`InsufficientPrivilege`가 나고 **기동 자체가 실패**한다(마이그레이션 계획서 A-01).

`DB_AUTO_MIGRATE` 환경변수로 이 DDL을 끌 수 있다.

| 값 | 동작 | 쓰는 곳 |
|---|---|---|
| `true` (기본) | 기동 시 DDL 실행 — **현재 온프렘 동작 그대로** | 온프렘, 로컬, CI |
| `false` | DDL 건너뛰고 기동. 스키마는 이미 있다고 가정 | RDS |

기본값을 `true`로 둔 이유: 이 PR로 운영 동작이 바뀌면 안 된다. RDS 배포에서만
`false`를 준다.

## 서비스별로 실행하는 DDL

`CREATE TABLE IF NOT EXISTS`는 SQLAlchemy `create_all()`이 모델에서 생성하므로
여기 옮겨 적지 않는다 — 모델이 바뀌면 이 문서가 조용히 틀려진다. 아래는 코드에
문자열로 박혀 있는 `ALTER` 문만 옮긴 것이다(그대로 실행 가능).

**diet-service** — `app/main.py` `_MEAL_LOG_COLUMN_MIGRATIONS`

```sql
ALTER TABLE service.meal_logs ADD COLUMN IF NOT EXISTS request_event_id UUID;
ALTER TABLE service.meal_logs ADD COLUMN IF NOT EXISTS vision_confidence NUMERIC(4,3);
ALTER TABLE service.meal_logs ADD COLUMN IF NOT EXISTS vision_provider VARCHAR(50);
ALTER TABLE service.meal_logs ADD COLUMN IF NOT EXISTS needs_user_confirmation BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE service.meal_logs ADD COLUMN IF NOT EXISTS vision_retryable BOOLEAN;
```

**community-service** — `app/main.py` `_ROOM_NUDGE_COLUMN_MIGRATIONS`

```sql
CREATE SCHEMA IF NOT EXISTS community;
ALTER TABLE community.room_nudges ADD COLUMN IF NOT EXISTS acknowledged_at TIMESTAMPTZ;
```

**login-service** — `app/main.py` `_USER_COLUMN_MIGRATIONS`
스키마 접두사를 붙이지 말 것. 이 서비스의 `users`/`social_accounts`/`admin_accounts`는
스키마를 명시한 적이 없고 연결의 `search_path`를 따른다. 접두사를 붙여
"relation does not exist"로 기동이 죽은 사고가 2026-07-21에 있었다.

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
```

**product-service** / **recipe-service**

```sql
CREATE SCHEMA IF NOT EXISTS product;   -- product-service
CREATE SCHEMA IF NOT EXISTS recipe;    -- recipe-service
```

**main-service**, **ingredients-service** — `create_all()`만. 별도 `ALTER` 없음.

## 이전 절차

1. 온프렘에서 스키마를 **실물 그대로** 뜬다. 모델에서 렌더링하지 말 것 —
   실제 운영 테이블에는 모델에 없는 컬럼이 있고(그 반대도 있다, `meal_items`의
   `serving_value` 사례) 실물이 정답이다.

   ```bash
   pg_dump --schema-only --no-owner --no-privileges -n service -n community -n product -n recipe zero > schema.sql
   ```

2. RDS에 스키마를 먼저 적용한다(관리자 role).
3. 앱 배포 환경변수에 `DB_AUTO_MIGRATE=false`를 준다.
4. 앱 role에는 DDL 권한을 주지 않는다 — `SELECT/INSERT/UPDATE/DELETE`만.
5. 이후 스키마 변경은 이 저장소가 아니라 DBA 절차로 처리한다.

## 커넥션 수 (C-2)

`DB_POOL_SIZE`(기본 5) / `DB_MAX_OVERFLOW`(기본 3)도 같이 환경변수로 뺐다.
파드당 상한 = `DB_POOL_SIZE + DB_MAX_OVERFLOW`.

현재 운영 합계는 약 128이고 온프렘 `zero-pg`의 `max_connections`는 200이라
여유가 있다. RDS `db.t4g.small`은 기본 `max_connections`가 약 225인데 백업·모니터링·
마이그레이션 세션이 함께 물리므로 여유가 크지 않다. 계획서 A-15대로
`DB_POOL_SIZE=2`, `DB_MAX_OVERFLOW=1`을 주면 16파드 × 3 = 48로 안전하다.

**기본값은 일부러 안 내렸다.** 부하 시점에 community-service가 파드당 8개 중 8개를
`idle in transaction`으로 잡고 있던 관측(감사 A-5)이 있어, 온프렘에서 지금 3으로
줄이면 `pool_timeout=10`에 걸려 500이 날 수 있다. 값 조정은 RDS 컷오버 때
파드 수·트래픽과 함께 결정한다.
