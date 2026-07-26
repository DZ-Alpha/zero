# DangDang isolated event pipeline

This is an additive proof-of-operation stack. It intentionally does not modify
the existing `zero` PostgreSQL database, `recipe.*` Kafka topics, or existing
Kafka/MinIO volumes.

## ⚠️ 의존관계 (반드시 읽을 것)

이 파이프라인은 **독립 배포 단위**지만 `infra/zero-infra`에 의존한다:

- Docker 네트워크 `zero-infra-backend`를 `external: true`로 참조한다.
  → **`infra/zero-infra`가 먼저 떠서 이 네트워크를 만들어야** 이 스택이 뜬다.
- Kafka(`zero-kafka`), MinIO(`zero-minio`), 그리고 outbox 발행 대상인
  zero PostgreSQL(`zero-pg-vector`)에 그 네트워크를 통해 접근한다.
- 이 스택 자체 상태 저장소는 `dangdang-pipeline-db`(별도 Postgres) 하나뿐이다.

즉 배포/기동 순서는 항상 **zero-infra → event-pipeline**.
K8s 이관 시에도 이 의존(공유 네트워크 대신 Service 이름, PVC 분리)을 반영해야 한다.

> 실제 배포 소스: 과거 zero-db 서버 `/opt/dangdang-event-pipeline-release-20260720`
> (git 미추적이던 것을 이 디렉터리로 편입). 서버의 `-release-20260719`,
> `-backup-*`, base 디렉터리는 옛 릴리스/백업 잔재이므로 참조하지 말 것.

## Isolation boundaries

- Kafka consumer group: `dangdang-vision-worker-v1`
- PostgreSQL container/volume: `dangdang-pipeline-db` / `dangdang-pipeline-db-data`
- API bind: `127.0.0.1:18080` only
- Existing Docker network: read/write access only to Kafka and a new
  `diet-photos` bucket in MinIO
- Existing topic retention, partitions, producer, and consumers are untouched

## Deployment

`/home/zero/.dangdang-pipeline.env` supplies the dedicated pipeline database password.

```bash
docker compose \
  -p dangdang-pipeline \
  --env-file /home/zero/.dangdang-pipeline.env \
  -f compose.yml config

docker compose \
  -p dangdang-pipeline \
  --env-file /home/zero/.dangdang-pipeline.env \
  -f compose.yml up -d --build
```

The isolated API mirrors the official diet contract:

- `POST /b/diet/upload?usr=...`
- `POST /b/diet/ai-analyze?usr=...`
- `GET /b/diet/ai-analyze?id=...&usr=...`
- `GET /b/diet/other-foods?id=...&usr=...`
- `DELETE /b/diet/upload/{id}`

Nutrition-label OCR is intentionally out of scope and `/b/diet/ocr-analyze` is
not registered. Run `scripts/smoke_test.sh` on the DB server. Promote the API
into the production diet-service only after the event contract and authentication
path are reviewed.

Always pass `-p dangdang-pipeline`; never use `--remove-orphans`. Keep the pipeline secret file outside the Docker build directory.

## Vision provider

The worker reads the claim-check image from the existing `diet-photos` bucket,
generates its result through a provider, then writes the existing completion
outbox record. No image bytes are placed in Kafka.

- `VISION_PROVIDER=gemini` is the ready-to-use provider. It requires
  `GEMINI_API_KEY`, uses `GEMINI_MODEL=gemini-flash-latest` by default, limits
  input to `VISION_MAX_IMAGE_BYTES` (10 MiB default), and returns a stable
  `list-diet` result.
- `VISION_PROVIDER=foodlens` requires the vendor-supplied REST recognition
  endpoint, authentication header, and multipart field name. FoodLens's public
  SDK says REST API access is obtained from support; the worker will not guess
  or call an undocumented endpoint. Configure `FOODLENS_API_URL`,
  `FOODLENS_TOKEN`, `FOODLENS_TOKEN_HEADER`, `FOODLENS_TOKEN_PREFIX`, and
  `FOODLENS_IMAGE_FIELD` then recreate only `dangdang-pipeline-worker`.

A completed result carries `needs_user_confirmation`. It is true when the
provider's confidence is below `VISION_CONFIDENCE_THRESHOLD` **or** when
`list-diet` is empty; Gemini does not reliably lower its own confidence for
non-food photographs, so an empty result is never treated as a confident one.

Transient provider failures (HTTP 429/5xx and connection errors) are retried up
to `VISION_MAX_ATTEMPTS` times with exponential backoff starting at
`VISION_RETRY_BACKOFF_SECONDS`. Permanent failures are not retried. The
`diet.photo.failed` event carries `retryable` so consumers can distinguish a
temporary quota exhaustion from a rejected image.

Secrets belong only in the out-of-repository, mode-600 environment file. Do
not use `docker inspect`, shell history, CI logs, or this README to store API
keys. If a key is pasted into chat or source control, revoke it and replace it
before deployment.

## User activity event consumer

`user.activity.raw` is consumed only by the optional `analytics` profile. It
uses PostgreSQL's integer `public.users.id` as `user_id`, writes `event_id` as
MongoDB `_id`, and tolerates duplicate delivery. It does not create or use a
MongoDB user table. Read `docs/PRODUCTION_VISION_ACTIVITY_HANDOFF.md` before
enabling it; producer outbox integration belongs in each backend service.
