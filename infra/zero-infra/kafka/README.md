# 저당 레시피 주기 수집 파이프라인 (kafka/)

producer(발견+Bedrock추출+게이트 → `recipe.parsed` 발행) → 두 컨슈머 그룹이 동시 소비:
`recipe-main`(적재+common영양+substituted 매칭/영양/합산/base) + `thumbnail`(완성샷→UPDATE).
자립형: `data_pipeline`을 import하지 않고 필요한 코드를 이 폴더에 복사해 완결.

- 설계: `docs/superpowers/specs/2026-07-18-kafka-periodic-pipeline-design.md`
- 계획: `docs/superpowers/plans/2026-07-18-kafka-periodic-pipeline.md`

## 구성

| 역할 | 실행 | 이미지 | 비고 |
|---|---|---|---|
| producer | 주기 배치(1회 실행 후 종료) | 슬림 | cron이 `docker compose run --rm producer` 호출 |
| consumer | 상시 데몬 | psycopg 등 | `recipe.parsed` → 적재+영양+매칭 |
| thumbnail | 상시 데몬 | **ffmpeg+yt-dlp** 포함(무거움) | `recipe.parsed` → 완성샷 → `/data/thumbnails` |

## 로컬 개발 (SSH 터널)

```bash
ssh -L 15432:10.10.20.10:5432 -L 6379:10.10.20.10:6379 \
    -L 19092:10.10.20.10:19092 zero@192.168.0.54
```
로컬 `.env`(repo 루트): DB `localhost:15432`, Redis `localhost:6379`(비번 %23 인코딩),
Kafka `localhost:19092`(LOCAL 리스너). 코드는 `.env`를 상위 경로에서 자동 탐색.

```bash
python -m kafka.producer.parse_producer 3     # 발견→발행
python -m kafka.consumer.recipe_consumer      # 소비→적재+영양+매칭 (상시)
python -m kafka.thumbnail.thumbnail_worker    # 썸네일 (상시)
```

## 서버 배포 (/opt/zero-infra)

전제: `opt/zero-infra/` 전체를 서버 `/opt/zero-infra/`에 반영. `kafka/` 폴더도
`/opt/zero-infra/kafka/`에 위치. `.env`는 서버용 값(전부 10.10.20.10, DATABASE_URL은
서버 내부 접속). AWS 자격증명은 서버 `~/.aws/credentials`에 둔다(compose가 마운트).

### 1. 인프라 기동 (데이터 보존 주의)

```bash
cd /opt/zero-infra
# ⚠️ 기존 개별 컨테이너가 떠 있으면 먼저 제거 (-v 절대 금지! 볼륨=데이터 보존)
docker stop zero-kafka zero-pg-vector 2>/dev/null
docker rm zero-kafka zero-pg-vector 2>/dev/null
# ⚠️ pg 데이터 볼륨명이 실제로 zero_pg_vector_data 인지 확인 (아니면 compose의 external name 수정)
docker volume ls | grep pg_vector_data

docker compose up -d kafka pg-vector redis minio mongodb
docker ps    # 5개 인프라 Up 확인
# 데이터 무손실 확인 (1697이 나와야 external 볼륨이 제대로 붙은 것)
docker exec zero-pg-vector psql -U <VECTOR_DB_USER> -d zero -c "SELECT count(*) FROM service.recipes;"
```

### 2. 토픽 생성 (최초 1회, kafka-data 볼륨 새로 만든 경우)

컨테이너 내부에서 INTERNAL 리스너로. (`kafka:29092`는 도커 DNS로 자기 자신 해석)

```bash
docker exec zero-kafka /opt/kafka/bin/kafka-topics.sh --create \
  --topic recipe.parsed --partitions 1 --replication-factor 1 --bootstrap-server kafka:29092
docker exec zero-kafka /opt/kafka/bin/kafka-topics.sh --create \
  --topic recipe.dlq --partitions 1 --replication-factor 1 --bootstrap-server kafka:29092
docker exec zero-kafka /opt/kafka/bin/kafka-topics.sh --list --bootstrap-server kafka:29092
```
> 토픽은 볼륨에 영속. 브로커를 껐다 켜도(`down`→`up`, `-v` 없이) 유지된다.

### 3. 앱 이미지 빌드 & 상시 데몬 기동

앱 컨테이너는 **non-root 유저(uid 10001)**로 실행된다. 사전 준비:

```bash
# (a) 썸네일 저장 폴더 생성 + non-root 유저가 쓸 수 있게 권한
sudo mkdir -p /opt/zero-infra/data/thumbnails
sudo chown -R 10001:10001 /opt/zero-infra/data/thumbnails   # 또는 chmod 777
# (b) AWS 자격증명이 $HOME/.aws/credentials 에 있어야 함(compose가 /home/app/.aws로 마운트)
ls ~/.aws/credentials
```

```bash
docker compose build producer consumer thumbnail   # 3개 이미지 빌드
docker compose up -d consumer thumbnail             # 상시 데몬만 up
docker compose logs -f consumer                     # 로그 확인(KST 타임스탬프)
```

> 이미지: producer/consumer는 슬림, thumbnail만 ffmpeg+yt-dlp 포함(무거움).
> 멀티스테이지는 우리 의존성 특성상 이득이 적어 미적용. 버전은 고정
> (requirements-*.txt, 2026-07-18 검증 버전).

### 4. producer 주기 실행 (cron)

producer는 상시가 아니라 1시간마다 1회. `crontab -e`에 등록:

```cron
0 * * * * cd /opt/zero-infra && /usr/bin/docker compose run --rm producer >> /opt/zero-infra/producer.log 2>&1
```

## 운영 메모

- **처리 시간**: 레시피 1건당 ~26초(substituted 매칭·영양이 병목). consumer 순차 처리.
- **max.poll.interval.ms=600000(10분)**: 재료 많은 레시피 대비 여유(kafka/config.py).
- **정량 환산**: 표준단위(t=5,T=15 등)는 코드(unit_converter)로 확정, 모호한 것만 LLM.
  감소율은 [-999.99,999.99] clamp(오버플로우로 consumer 죽는 것 방지).
- **producer 주기 근거**: YouTube 쿼터(1시간마다 search 2,400/일 « 10,000) + 신규 빈도
  (하루 1~2건) 균형. 키워드 늘리면 쿼터 재계산.

## 2단계 ↔ 다중토픽 비교 (향후)

현재 2단계(recipe.parsed 하나 + 두 그룹 동시 소비). 추후 단계별 다중토픽과 처리량/지연/
실패율/코드량으로 비교. 상세는 설계 문서 §8.
