## Ansible managed
# pg-vector pgBackRest 복구 런북

repository는 zero-db의 로컬 MinIO에 있다. PostgreSQL 논리 장애와 PGDATA 손상에는 복구할 수 있지만 DB VM/물리 서버와 MinIO가 함께 소실되면 복구할 수 없다.

## 평시 확인

    docker exec zero-pg-vector pgbackrest --stanza=pgvector --config=/etc/pgbackrest/pgbackrest.conf info
    systemctl status pgbackrest-full.timer pgbackrest-incr.timer --no-pager

## 격리 최신 복구

운영 볼륨 `zero_pg_vector_data`를 절대로 지정하지 않는다. 이름은 새 날짜/번호로 만들고 기존 테스트 자원과 충돌하지 않는지 먼저 inspect한다.

    export RESTORE_VOLUME=dangdang-pitr-restore-latest-YYYYMMDD
    export RESTORE_CONTAINER=dangdang-pitr-restore-latest-YYYYMMDD
    docker container inspect "$RESTORE_CONTAINER"  # 존재하면 중단
    docker volume inspect "$RESTORE_VOLUME"        # 존재하면 중단
    docker volume create "$RESTORE_VOLUME"
    docker run --rm --user root -v "$RESTORE_VOLUME":/restore zero-infra/pg-vector-pgbackrest:pg17-20260719 chown -R 999:999 /restore
    docker run --rm --network zero-infra-backend --user 999:999 \
      -v "$RESTORE_VOLUME":/var/lib/postgresql/data \
      -v /opt/zero-infra/config/pgbackrest/pgbackrest.conf:/etc/pgbackrest/pgbackrest.conf:ro \
      zero-infra/pg-vector-pgbackrest:pg17-20260719 pgbackrest --stanza=pgvector --config=/etc/pgbackrest/pgbackrest.conf --archive-mode=off restore
    docker run -d --name "$RESTORE_CONTAINER" --network zero-infra-backend \
      -v "$RESTORE_VOLUME":/var/lib/postgresql/data \
      -v /opt/zero-infra/config/pgbackrest/pgbackrest.conf:/etc/pgbackrest/pgbackrest.conf:ro \
      zero-infra/pg-vector-pgbackrest:pg17-20260719
    docker exec "$RESTORE_CONTAINER" pg_isready
    docker network disconnect zero-infra-backend "$RESTORE_CONTAINER"

초기 recovery 동안만 내부 network가 필요하며 host port는 publish하지 않는다. 검증 후 network를 disconnect한다. 시간 target은 target 이후 commit/WAL이 repository에 없으면 PostgreSQL이 안전 실패하므로, 사고 조사에서 확인된 time/LSN만 사용한다.

테스트 자원도 승인 없이 삭제하지 않는다. 운영 복구는 사고 시각, 목표 time/LSN, 현재 PGDATA 보존 방법, 사전 dump를 별도 승인한 뒤 수행한다. 운영 PGDATA 대상 무승인 `--delta restore`, `compose down -v`, volume 삭제는 금지한다.

## 롤백

base Compose backup과 `zero-infra/pg-vector:rollback-20260719`를 사용하되 동일 `zero_pg_vector_data` volume을 유지한다. dump 복원은 마지막 수단이며 운영 DB에 자동 실행하지 않는다.
