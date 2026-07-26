# DangDang 개발팀 병합 요청 — 실동작 Vision·행동 이벤트 연결

## 이미 인프라/DB에 적용됨

- `user.activity.raw` Kafka 토픽: 6 partitions, 7-day retention, single broker RF=1.
- PostgreSQL `service.event_outbox` 생성 완료.
- PostgreSQL `service.meal_logs`에 `vision_confidence`, `vision_provider`,
  `needs_user_confirmation` 추가 완료. 상태 CHECK에
  `AWAITING_CONFIRMATION` 추가 완료.
- `dangdang-pipeline-worker`: Gemini Vision 이미지로 실행 중.
- `dangdang-activity-mongodb-consumer`: 실행 중. `user.activity.raw`를
  `dangdang_analytics.user_activity_events`로 idempotent 적재.
- Mongo `_id`는 `event_id(UUIDv7)`이고 사용자 식별자는 PostgreSQL
  `public.users.id` 정수값이다. Mongo 사용자 PK를 만들거나 쓰지 않는다.

DB migration은 이미 적용됐으므로 서비스 PR에서 재실행하지 말 것.

## 현재 막힌 실제 연결

`/home/zero/dev/zero` 원본은 이 작업에서 수정하지 않았다. 현재 프론트는
`frontend/app/api/upload/route.ts`에서 사진을 `public/uploads`에 저장하고,
diet-service는 요청 handler에서 Claude를 동기 호출한다. 이 상태는 MinIO →
Kafka → Gemini worker와 연결되지 않는다.

## 백엔드 필수 구현

### 1. 공통 outbox publisher

모든 업무 이벤트는 DB 업무 변경과 **같은 transaction**에서
`service.event_outbox`에 INSERT한다. request handler에서 Kafka로 직접 발행 금지.

필수 envelope:

```json
{
  "event_id": "UUIDv7",
  "event_type": "user.diet.analysis_requested",
  "user_id": 42,
  "occurred_at": "ISO-8601 UTC",
  "producer": "diet-service",
  "schema_version": 1,
  "trace_id": "optional",
  "properties": {"meal_log_id": "UUID"}
}
```

- `user_id`는 반드시 인증 JWT `payload["user_id"]`.
- Kafka key는 `str(user_id)`.
- producer 설정: `enable.idempotence=true`, `acks=all`.
- publisher는 unpublished rows를 `FOR UPDATE SKIP LOCKED`로 가져오고 Kafka ACK 후
  `published_at`을 갱신한다. 중복 전달은 정상이며 `event_id`가 dedup key다.
- payload에 JWT, email, 생년월일, 신체정보, 이미지 byte/key/URL, 검색어/자유문자열 금지.

### 2. 서비스별 업무 이벤트

| 서비스 | transaction 성공 후 발행 |
|---|---|
| login-service | `user.auth.login_succeeded`, `user.auth.logout`, `user.profile.created` |
| diet-service | `user.diet.photo_uploaded`, `user.diet.analysis_requested`, `user.diet.analysis_completed`, `user.diet.analysis_failed`, `user.diet.meal_confirmed`, `user.diet.meal_deleted` |
| main-service | `user.profile.updated`, `user.health_profile.updated`, `user.preference.updated` |
| product-service | `user.product.favorite_added`, `user.product.favorite_removed` |
| recipe-service | `user.recipe.favorite_added`, `user.recipe.favorite_removed` |
| community-service | `user.community.notice_liked`, `user.community.notice_unliked` |

### 3. 프론트 UI telemetry 수신 API

gateway에 `POST /b/activity/events`를 추가한다. 프론트는 `user.ui.*` 이벤트만
batch로 전송한다. server는 JWT에서 사용자 ID를 넣고 outbox transaction으로 기록한다.

- max 20 events/request, max 8 KiB/event
- type/property allow-list, rate limit 적용
- client payload의 `user_id`, `producer`는 무시/거부
- `202 Accepted` 반환
- 매 keystroke/raw search query는 보내지 않는다

## Vision 필수 구현

### 1. 프론트 업로드 교체

`frontend/app/api/upload/route.ts`는 브라우저 파일을 server-side MinIO
`diet-photos` bucket에 쓰고 `minio://diet-photos/{object_key}`만 반환한다.
브라우저에 MinIO credential/presigned write URL을 노출하지 않는다. 기존
`frontend-uploads` volume은 migration 당일 삭제하지 않는다.

### 2. diet-service 비동기화

1. `/diet/upload`은 MinIO key를 검증하고 `meal_logs` 생성 + outbox
   `diet.photo.requested`를 같은 transaction으로 기록.
2. Vision worker 결과는 인증된 internal callback으로 diet-service에 전달.
3. callback은 event idempotency를 확인한 뒤 `meal_items`, confidence 컬럼,
   상태, completed/failed outbox를 같은 transaction으로 기록.
4. `confidence < 0.75` 또는 음식 미검출이면
   `AWAITING_CONFIRMATION` + `needs_user_confirmation=true`.
5. `POST /b/diet/ai-analyze/{meal_log_id}/confirm`에서 소유자 JWT 검증 후
   사용자가 수정한 항목을 확정하고 `COMPLETED` 및
   `user.diet.meal_confirmed` 이벤트 발행.

## 프론트 필수 구현

- `DietAnalysisResponse`에 `confidence`, `confidence_source`,
  `needs_user_confirmation`, `PENDING|PROCESSING|AWAITING_CONFIRMATION|DONE|FAILED`
  상태 추가.
- `RecordMealModal`은 분석 중 1/2/3/5초 bounded polling(최대 60초)을 한다.
  pending은 오류가 아니다.
- low confidence는 “사진 인식 확신이 낮아요” editable draft 화면을 보이고,
  사용자 confirm 전에는 식단을 완료 처리하지 않는다.
- UI event는 `/b/activity/events`만 호출한다. Kafka/Mongo 직접 연결 금지.

## 검증 기준

1. 실제 사용자 1명으로 사진 1장: MinIO object key만 Kafka에 존재.
2. 동일 `event_id` 재소비: Mongo 문서 1개, 결과/meal item 중복 없음.
3. worker가 DB 반영 전 죽음: 재소비 성공. 반영 후 죽음: 중복 반영 없음.
4. low/high confidence UX와 확정 API 검증.
5. 업무 이벤트와 UI event가 각각 Mongo에 적재되고 개인정보 payload 없음.
6. `dangdang-activity-mongodb-v1` lag 및 worker lag 0 확인.

## 참고 구현물

- 이벤트 schema: `contracts/user.activity.raw.v1.json`
- Mongo consumer: `app/activity_consumer.py`
- Gemini + confidence worker: `app/vision.py`, `app/worker.py`
- 현재 실행 파이프라인 경로: `/opt/dangdang-event-pipeline-release-20260720`

`/home/zero/dev/zero`은 원본 확인용이므로 이 인프라 작업에서 수정하지 않았다.
