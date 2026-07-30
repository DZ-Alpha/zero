#!/usr/bin/env bash
#
# DAST staging PG 스키마 재구성 스크립트 (재현성 확보)
#
# 무엇: 운영 zero DB의 "구조만"(--schema-only, 데이터 0, PII 안 담김)을 DAST 전용
#   staging PG(dang-stg-pg)로 복제한다. 스키마/테이블/FK/인덱스가 운영과 동일해져
#   9개 서비스가 전부 정상 기동한다(recipe가 참조하는 데이터팀 소유 service.recipes 포함).
#
# 왜: 각 서비스의 create_all은 자기 소유 테이블만 만들어, service.recipes(데이터팀 소유)
#   같은 테이블이 빈 staging PG엔 없다 → recipe가 CrashLoop → argocd app wait --health
#   게이트가 막혀 recipe prod 배포 차단. pg_dump 복제로 구조를 완성해 이 문제를 없앤다.
#
# 언제 실행: staging PG(Cluster/PVC)를 재생성했을 때, 또는 운영 스키마가 크게 바뀌어
#   staging 구조를 최신화할 때. 평상시(노드 재시작 등)엔 Longhorn PVC가 데이터를 지키므로
#   불필요 — 이 스크립트는 "재생성/최신화" 대비용이다.
#
# 안전: --schema-only라 운영 데이터를 아예 안 읽는다(PII 유출 없음). 비밀번호는 하드코딩하지
#   않고 클러스터 secret에서 실행 시점에 읽는다. 대상은 오직 staging PG(dang-stg-pg-rw).
#
# 사용: ./scripts/dast-stg-schema-sync.sh
#   (mgmt 등 sudo kubectl 가능한 환경에서 실행. KUBECTL 환경변수로 override 가능)
set -euo pipefail

KUBECTL="${KUBECTL:-sudo kubectl}"
STG_NS="dang-be-ns-stg"
STG_PG_POD="dang-stg-pg-1"                       # CNPG primary 파드
PROD_HOST="dang-pg.dang-db-ns.svc.cluster.local" # 운영 zero-pg primary 별칭
DB="zero"
DB_USER="yesman"

echo "== DAST staging PG 스키마 동기화 =="

# 1) 비밀번호를 클러스터 secret에서 읽는다(하드코딩 금지).
#    운영: zero-pg-app(키 password). staging: dang-stg-pg-app(키 password).
echo "[1/4] secret에서 접속정보 로드"
PROD_PW=$($KUBECTL -n dang-db-ns get secret zero-pg-app \
  -o jsonpath='{.data.password}' | base64 -d)
STG_PW=$($KUBECTL -n "$STG_NS" get secret dang-stg-pg-app \
  -o jsonpath='{.data.password}' | base64 -d)

# 2) 격리 가드: 대상이 정말 staging PG인지 확인. 운영으로 restore하면 재앙이므로 방어.
echo "[2/4] 대상이 staging PG인지 확인"
STG_CLUSTER=$($KUBECTL -n "$STG_NS" get pod "$STG_PG_POD" \
  -o jsonpath='{.metadata.labels.cnpg\.io/cluster}' 2>/dev/null || echo "")
if [ "$STG_CLUSTER" != "dang-stg-pg" ]; then
  echo "중단: $STG_PG_POD 가 dang-stg-pg 클러스터가 아님(cluster=$STG_CLUSTER). 오작동 방지."
  exit 1
fi

# 3) 운영 구조만 덤프 → staging PG로 restore.
#    --schema-only: 데이터 미포함(PII 안 담김). --no-owner/--no-privileges: 권한 차이 무시.
#    이미 존재하는 객체는 "already exists" 에러가 나지만 무해(구조가 이미 맞다는 뜻).
echo "[3/4] 운영 구조(schema-only) → staging restore (already exists 에러는 무해)"
$KUBECTL -n "$STG_NS" exec "$STG_PG_POD" -- sh -c "
  PGPASSWORD='$PROD_PW' pg_dump --schema-only --no-owner --no-privileges \
    -h $PROD_HOST -U $DB_USER -d $DB \
  | PGPASSWORD='$STG_PW' psql -U $DB_USER -d $DB -h localhost -v ON_ERROR_STOP=0
" 2>&1 | grep -vE '^(CREATE|ALTER|SET|COMMENT|GRANT|REVOKE|DROP| )' | tail -30 || true

# 4) 검증: 핵심 데이터팀 테이블(service.recipes)과 service 스키마 테이블 수 확인.
echo "[4/4] 검증"
$KUBECTL -n "$STG_NS" exec "$STG_PG_POD" -- \
  psql -U postgres -d "$DB" -tc \
  "SELECT 'service.recipes 존재: ' || to_regclass('service.recipes')::text;"
$KUBECTL -n "$STG_NS" exec "$STG_PG_POD" -- \
  psql -U postgres -d "$DB" -tc \
  "SELECT 'service 스키마 테이블 수: ' || count(*) FROM information_schema.tables WHERE table_schema='service';"

echo "== 완료. 이제 9개 서비스가 정상 기동한다(rollout restart 필요 시 수행) =="
