# zero-infra

Ubuntu 서버에서 MinIO, MongoDB, Redis를 Docker Compose로 운영하는 프로젝트입니다.
정형 데이터베이스는 로컬 컨테이너를 만들지 않고 더존비즈온 제공 외부 PostgreSQL만 사용합니다.
Kafka는 나중에 같은 `compose.yml`의 `backend` 네트워크와 named volume 구조로 추가합니다.

## ⚠️ 이 디렉터리에 의존하는 것

`event-pipeline`(레포 루트)이 이 스택에 의존합니다:

- `event-pipeline`은 여기서 만드는 Docker 네트워크 `zero-infra-backend`를
  `external: true`로 참조해 Kafka/MinIO/zero-PostgreSQL에 접근합니다.
- 따라서 기동 순서는 항상 **zero-infra 먼저 → event-pipeline 나중**.

## 구성 요소

이 디렉터리는 데이터 플랫폼 + 레시피 Kafka 워커까지 **한 compose 배포 단위**입니다:

- 데이터 플랫폼: MinIO, MongoDB, Redis, Kafka, pg-vector(PITR 포함)
- `kafka/`: 레시피 크롤러(producer) / 컨슈머(영양성분 채우기) / 썸네일 워커
  — `compose.yml`에서 `build: ./kafka/...`로 이 스택과 함께 빌드·배포됨

> 실제 배포 소스: 과거 zero-db 서버 `/opt/zero-infra` (git 미추적이던 것을 편입).
> 시크릿(`.env`, `tls.key`, 실제 `pgbackrest.conf`)과 생성 데이터(`data/thumbnails`)는
> 제외했으며, `config/pgbackrest/pgbackrest.conf.example`이 치환본입니다.

## 보안 및 저장 위치

- 로컬 서비스 계정과 비밀번호는 최초 설치 시 터미널에서 직접 지정합니다.
- 실제 비밀번호는 `.env`에만 있으며 파일 권한은 `600`입니다.
- `.env`를 Git, 메신저, 문서에 복사하지 마십시오.
- MinIO와 MongoDB 포트는 모두 `127.0.0.1`에만 바인딩됩니다.
- MinIO 데이터는 `zero-infra-minio-data` named volume을 사용합니다.
- MongoDB 데이터는 `zero-infra-mongodb-data` named volume을 사용합니다.
- Redis 데이터는 `zero-infra-redis-data` named volume과 AOF 영속화를 사용합니다.
- 이 서버에는 PostgreSQL 서버나 PostgreSQL 컨테이너를 설치하지 않습니다.
- `postgresql-client`는 외부 더존 PostgreSQL 접속 테스트에만 사용합니다.
- Docker Root Dir은 `/var/lib/docker`이며 별도 158GB XFS 파티션입니다.
- named volume은 백업이 아닙니다. 별도 디스크나 원격 저장소에 백업해야 합니다.

## 파일 구조

```text
/opt/zero-infra/
├── compose.yml
├── .env                 # 실제 비밀번호, chmod 600
├── .env.example         # 비밀번호가 없는 예시
├── .gitignore
├── README.md
└── config/
    ├── minio/
    ├── mongodb/
    └── kafka/
```

## 서비스 관리

Docker 그룹 권한은 다음 SSH 로그인부터 적용됩니다. 현재 세션에서는 `sudo`를 사용하십시오.

```bash
cd /opt/zero-infra
docker compose ps
docker compose logs --tail=100 minio
docker compose logs --tail=100 mongodb
docker compose logs --tail=100 redis
docker compose pull
docker compose up -d
```

서비스 중지는 `docker compose stop`, 재시작은 `docker compose restart`를 사용합니다.
데이터 삭제를 동반하는 `docker compose down -v`는 실행하지 마십시오.

## 로컬 MinIO 접속

서버 내부:

```bash
curl -f http://127.0.0.1:9000/minio/health/live
```

원격 PC에서는 SSH 터널을 사용합니다:

```bash
ssh -L 9000:127.0.0.1:9000 -L 9001:127.0.0.1:9001 zero@192.168.0.54
```

터널 연결 후 브라우저에서 `http://127.0.0.1:9001`을 엽니다.
직접 지정한 아이디와 비밀번호는 서버의 `.env`에 저장되어 있으며 README에는 기록하지 않습니다.

## 로컬 MongoDB 접속

서버에서 컨테이너의 `mongosh`를 사용하면 비밀번호를 대화식으로 요청합니다:

```bash
docker exec -it zero-mongodb mongosh --username <MONGO_INITDB_ROOT_USERNAME> --password --authenticationDatabase admin
```

원격 PC의 MongoDB 클라이언트를 사용하려면 먼저 SSH 터널을 연결합니다:

```bash
ssh -L 27017:127.0.0.1:27017 zero@192.168.0.54
mongosh --host 127.0.0.1 --port 27017 --username <MONGO_INITDB_ROOT_USERNAME> --password --authenticationDatabase admin
```

MongoDB 27017 포트는 외부에 직접 공개하지 않습니다.

## 로컬 Redis 접속

서버에서 비밀번호를 셸 히스토리에 남기지 않고 접속합니다:

```bash
cd /opt/zero-infra
sudo docker compose exec redis sh
REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli
```

원격 PC에서는 SSH 터널 `ssh -L 6379:127.0.0.1:6379 zero@<서버-IP>`을 사용합니다.
Redis 6379 포트는 외부에 직접 공개하지 않습니다.

## 더존비즈온 제공 자원

각 프로젝트 그룹별 제공 자원:

| 구분 | 사양/정보 |
|---|---|
| Database 서버 | core 4, memory 4GB, disk 100GB |
| FTP 서버 | core 4, memory 4GB, disk 500GB |
| 파일 전송 | SFTP |
| 데이터베이스 | PostgreSQL |
| TEAM1 IP | `211.46.52.151` |
| TEAM1 ID | `team1` |
| TEAM1 DB명 | `postgres` |
| SFTP 포트 | `2022` |
| DB 포트 | `15432` |

SFTP 접속:

```bash
sftp -P 2022 team1@211.46.52.151
```

PostgreSQL 접속:

```bash
psql -h 211.46.52.151 -p 15432 -U team1 -d postgres
```

두 명령 모두 더존에서 받은 기존 비밀번호를 대화식으로 입력합니다. 외부 비밀번호는 `.env`나 README에 저장하지 않습니다.
이 서버에서는 outbound 접속만 사용하므로 inbound 2022/15432 UFW 규칙은 필요하지 않습니다.

인증 전 TCP 연결 가능 여부만 확인하려면:

```bash
timeout 5 bash -c '</dev/tcp/211.46.52.151/2022' && echo reachable || echo unreachable
timeout 5 bash -c '</dev/tcp/211.46.52.151/15432' && echo reachable || echo unreachable
```

## Kafka 추가 원칙

- 서비스 이름은 `kafka`, 컨테이너 이름은 `zero-kafka`를 사용합니다.
- 기존 `backend` 네트워크에 연결합니다.
- `zero-infra-kafka-data`라는 named volume을 정의합니다.
- 데이터 마운트 경로는 선택한 Kafka 이미지의 공식 문서에 맞춥니다.
- retention과 로그 크기 제한을 반드시 설정합니다.
- 외부 공개가 필요할 때 advertised listener와 방화벽 정책을 함께 검토합니다.

## 운영 주의사항

- 현재 Nextcloud Snap이 루트 파티션의 `/var/snap/nextcloud`에 데이터를 저장합니다.
- 루트와 `/var/lib/docker` 모두 디스크 사용률을 모니터링하십시오.
- 외부 PostgreSQL의 백업·복구 정책은 더존 제공 범위와 프로젝트 정책을 함께 확인하십시오.
- MongoDB까지 포함하고 나중에 Kafka도 운영할 경우 현재 8GB RAM은 매우 빠듯할 수 있습니다.
