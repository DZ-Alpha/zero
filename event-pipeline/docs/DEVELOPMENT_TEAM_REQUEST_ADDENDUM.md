# 개발팀 요청서 추가분 — 정정 2건과 사용자 행동 이벤트 흐름

앞서 전달한 요청서에 **사실과 다른 항목 2건**이 있습니다. 이미 그 내용대로
구현하셨다면 아래 정정을 먼저 확인해 주세요. 그 뒤에 요청서에서 흐름 예시가
빠져 있던 사용자 행동 이벤트 파이프라인을 같은 형식으로 적었습니다.

인프라 쪽 검증은 끝났습니다. 실제 사진 40장으로 MinIO → Kafka → Gemini →
PostgreSQL → Kafka 전 구간과 Kafka → MongoDB 전 구간을 실행했고, 파이프라인
자체 검사 24건은 모두 통과했습니다.

---

## 정정 1 — worker는 callback을 호출하지 않습니다 (긴급)

앞선 요청서 `Vision 필수 구현 > 2. diet-service 비동기화` 5번에
"worker callback은 인증된 internal callback으로 diet-service에 전달"이라고
적었습니다. **이 callback은 구현되어 있지 않고, 구현할 계획도 없습니다.**

worker는 결과를 자기 DB outbox에 기록한 뒤 **Kafka 토픽으로 발행**합니다.
callback 수신 엔드포인트를 만드셨다면 호출되지 않습니다. 폐기하고 consumer로
바꿔 주세요.

```
diet-service는 Kafka consumer로 `diet.photo.completed`, `diet.photo.failed`를
구독한다.

- consumer group: diet-service 전용으로 신설
- enable.auto.commit=false, DB 반영 후 수동 commit
- 멱등키는 `causation_event_id` (= diet-service가 발행한 요청 이벤트의 event_id)
```

`diet.photo.completed` 실제 페이로드:

```json
{
  "event_id": "UUIDv7",
  "causation_event_id": "요청 이벤트의 event_id",
  "analysis_id": "UUID",
  "upload_id": "UUID",
  "user_id": "요청 때 보낸 값이 그대로 반사됨",
  "result_ref": "analysis:{analysis_id}",
  "result": {
    "path": "food_photo_gemini",
    "list-diet": [
      { "name": "라멘", "calo": 550, "dang": 4,
        "ingred-list": [ { "name": "면", "amount": 150 },
                         { "name": "육수", "amount": 350 } ] }
    ],
    "confidence": 0.95,
    "confidence_source": "model_self_assessment",
    "needs_user_confirmation": false,
    "object_size": 51989
  },
  "processor_version": "gemini-activity-v1",
  "completed_at": "ISO-8601",
  "schema_version": 1
}
```

`diet.photo.failed`:

```json
{
  "event_id": "UUIDv7",
  "causation_event_id": "...",
  "analysis_id": "UUID",
  "user_id": "...",
  "error_code": "GEMINI_HTTP_429 | GEMINI_INVALID_JSON | OBJECT_NOT_READABLE | IMAGE_TOO_LARGE | IMAGE_EMPTY | INVALID_EVENT",
  "attempt_count": 1,
  "retryable": false,
  "failed_at": "ISO-8601",
  "schema_version": 1
}
```

`retryable=true`는 일시적 오류이므로 사용자에게 재시도 UI를 보여주세요.
`false`는 영구 실패입니다.

## 정정 2 — user_id 타입이 토픽마다 다릅니다

| 토픽 | user_id 타입 | 예시 |
|---|---|---|
| `diet.photo.requested` | **문자열** | `"42"` |
| `user.activity.raw` | **정수** | `42` |

`diet.photo.requested`에 정수를 보내면 worker의 스키마 검증에서 거부되어
`INVALID_EVENT`로 DLQ에 떨어집니다. 파이프라인의 `diet_analysis_jobs.user_id`
컬럼이 `text`라서 그렇습니다. 앞서 보낸 예시 코드에 `user_id=user_id`로만
적혀 있었으니, 요청 이벤트에는 `str(user_id)`로 넣어 주세요.

`user.activity.raw`는 반대로 정수만 받습니다. MongoDB에 적재될 때도 정수
`public.users.id`입니다.

---

## 사용자 행동 이벤트 흐름 — 사용자 42의 하루

앞선 요청서에 서비스별 이벤트 표만 있고 흐름 예시가 없어 추가합니다.

```
1. 사용자 42가 로그인한다.
   login-service는 인증 성공 transaction 안에서 service.event_outbox에
   `user.auth.login_succeeded`를 INSERT한다. 로그인 응답은 commit 뒤에 반환한다.

2. outbox publisher가 unpublished row를 FOR UPDATE SKIP LOCKED로 집어
   `user.activity.raw`에 발행하고, Kafka ACK 뒤에 published_at을 갱신한다.
   Kafka key는 str(user_id)이고 producer는 enable.idempotence=true, acks=all.

3. 사용자가 식단 사진을 올린다. diet-service는 meal_logs 생성과 동시에
   `user.diet.photo_uploaded`를 같은 transaction의 outbox에 넣는다.
   사진 분석 요청(diet.photo.requested)은 이와 별개의 이벤트다.

4. 사용자가 상품을 즐겨찾기한다. product-service가
   `user.product.favorite_added`를 발행한다.

5. 사용자가 화면을 스크롤하고 탭을 전환한다. 프론트는 이 UI 이벤트를
   모아 `POST /b/activity/events`로 batch 전송한다. gateway가 JWT에서
   user_id를 채워 outbox에 기록한다. 브라우저는 Kafka에 직접 붙지 않는다.

6. Mongo consumer가 `user.activity.raw`를 소비해
   dangdang_analytics.user_activity_events에 `_id = event_id`로 적재한다.
   같은 event_id가 다시 와도 문서는 1개다.
```

### 공통 outbox 헬퍼

모든 업무 이벤트는 업무 DB 변경과 **같은 transaction**에서 기록합니다.
request handler에서 Kafka로 직접 발행하지 마세요.

```python
async def enqueue_activity(session, *, event_type, user_id, producer, properties, trace_id=None):
    """service.event_outbox에 user.activity.raw 이벤트를 넣는다.

    user_id는 반드시 JWT payload["user_id"]에서 온 정수 public.users.id.
    properties에 JWT, email, 생년월일, 신체정보, 이미지 byte/key/URL,
    검색어 원문을 넣지 않는다.
    """
    event_id = uuid7()
    session.add(EventOutbox(
        event_id=event_id,
        topic="user.activity.raw",
        event_key=str(user_id),
        payload={
            "event_id": str(event_id),
            "event_type": event_type,      # 반드시 "user." 로 시작
            "user_id": int(user_id),       # 정수. 문자열이면 consumer가 거부
            "occurred_at": utcnow_iso8601(),
            "producer": producer,          # 반드시 "-service" 로 끝남
            "schema_version": 1,
            "trace_id": trace_id,
            "properties": properties,
        },
    ))
```

호출부는 이렇게 됩니다.

```python
async def login(credentials, session):
    async with session.begin():
        user = await authenticate(session, credentials)
        await enqueue_activity(
            session,
            event_type="user.auth.login_succeeded",
            user_id=user.id,
            producer="login-service",
            properties={"method": "password"},
        )
    return issue_tokens(user)          # commit 이후에만 응답
```

### 프론트 UI telemetry

```ts
// user.ui.* 이벤트만. Kafka/Mongo 직접 연결 금지.
await api.post('/b/activity/events', {
  events: [
    { event_type: 'user.ui.screen_viewed', occurred_at: iso(), properties: { screen: 'diet_home' } },
    { event_type: 'user.ui.tab_changed',   occurred_at: iso(), properties: { tab: 'weekly' } },
  ],
});
// 응답은 202. user_id 와 producer 는 보내도 서버가 무시한다.
// 최대 20건/요청, 8 KiB/건. 매 keystroke 나 검색어 원문은 보내지 않는다.
```

### MongoDB에 적재되는 최종 형태

```json
{
  "_id": "UUIDv7 event_id",
  "event_type": "user.diet.meal_confirmed",
  "user_id": 42,
  "occurred_at": "2026-07-20T08:31:00Z",
  "producer": "diet-service",
  "schema_version": 1,
  "properties": { "meal_log_id": "..." }
}
```

`user_id`는 Mongo 사용자 `_id`가 아니라 PostgreSQL `public.users.id` 정수입니다.
Mongo에 사용자 PK를 새로 만들지 마세요.

---

## 변경된 파이프라인 API 응답

`GET /b/diet/ai-analyze`가 confidence 관련 필드를 반환하도록 바꿨습니다.
이전에는 `list-diet`만 반환해서 프론트가 confidence 분기를 구현할 수
없었습니다. 기존 필드는 그대로이므로 호환됩니다.

```json
{
  "id": "...", "status": "DONE",
  "list-diet": [ ... ],
  "confidence": 0.95,
  "confidence_source": "model_self_assessment",
  "needs_user_confirmation": false
}
```

`needs_user_confirmation`은 **confidence가 임계값 미만이거나 음식이 하나도
검출되지 않은 경우** true입니다. 모델이 빈 결과에 confidence 0.95를 붙여
답하는 사례가 실제로 있어, 신뢰도만으로 분기하면 안 됩니다.

---

## 실측 운영 수치 (실사진 40장 기준)

| 항목 | 값 |
|---|---|
| 성공률 | 39/40 (97.5%) |
| 실패 | `GEMINI_INVALID_JSON` 1건 |
| worker 처리율 | **분당 약 11건** |
| 사진당 평균 소요 | 약 5.6초 |
| 429 발생 | 0건 (유료 티어) |

**worker는 Kafka 메시지를 순차 처리합니다.** 동시 업로드가 몰리면 큐가
분당 11건 속도로만 빠집니다. 100명이 동시에 올리면 마지막 사용자는 약 9분을
기다립니다. 프론트 polling 타임아웃을 60초로 잡으면 부하 시 정상 건도
타임아웃으로 보입니다. 다음 중 하나가 필요합니다.

- 프론트가 `PENDING`을 오류로 취급하지 않고 계속 대기 (권장)
- worker 수평 확장 (Kafka 파티션이 3개이므로 최대 3배)

---

## 남은 확인 사항

- `GEMINI_INVALID_JSON`이 40건당 1건꼴로 일정하게 발생합니다. 현재
  `retryable=false`이지만 모델 응답은 비결정적이라 재시도 대상 전환을
  검토 중입니다. 전환하면 별도 공지하겠습니다.
- 429 재시도 로직은 구현·단위검증 완료이나, 유료 티어에서 429가 재현되지
  않아 실트래픽 검증은 아직입니다.
- `user.activity.raw`에 발행하는 코드는 현재 **한 줄도 없습니다.** Mongo
  consumer와 토픽, 테이블은 준비되어 대기 중입니다.
