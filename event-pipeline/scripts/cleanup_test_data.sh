#!/usr/bin/env bash
# Remove only the synthetic rows and objects created by the E2E and load
# harnesses. The vision-qa/food101-* corpus is the source image set those
# harnesses clone from and is deliberately left in place.
#
# Run on zero-db. Prints counts before and after; pass --apply to delete.
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-dangdang-pipeline-db}"
MINIO_CONTAINER="${MINIO_CONTAINER:-zero-minio}"
MONGO_CONTAINER="${MONGO_CONTAINER:-zero-mongodb}"
CONSUMER_CONTAINER="${CONSUMER_CONTAINER:-dangdang-activity-mongodb-consumer}"
TEST_USER_ID="${TEST_USER_ID:-424242}"
APPLY="${1:-}"

MATCH="image_key LIKE 'vision-qa/load-%' OR image_key LIKE 'vision-qa/e2e-%' OR image_key LIKE 'e2e/%'"

psql() { sudo docker exec -i "$DB_CONTAINER" psql -U pipeline -d pipeline -v ON_ERROR_STOP=1 "$@"; }

echo "== 삭제 대상 =="
psql -c "SELECT count(*) AS test_uploads FROM diet_uploads WHERE ${MATCH};"
psql -c "SELECT count(*) AS test_jobs FROM diet_analysis_jobs j
         JOIN diet_uploads u USING (upload_id) WHERE ${MATCH/image_key/u.image_key};"
echo "== 보존 대상 (원본 이미지 세트) =="
psql -c "SELECT count(*) AS kept FROM diet_uploads WHERE NOT (${MATCH});"

if [ "$APPLY" != "--apply" ]; then
  echo
  echo "미리보기입니다. 실제로 지우려면: $0 --apply"
  exit 0
fi

echo
echo "== PostgreSQL 정리 =="
psql <<SQL
BEGIN;
CREATE TEMP TABLE doomed ON COMMIT DROP AS
  SELECT upload_id FROM diet_uploads WHERE ${MATCH};
DELETE FROM processed_events WHERE job_id IN
  (SELECT analysis_id FROM diet_analysis_jobs WHERE upload_id IN (SELECT upload_id FROM doomed));
DELETE FROM diet_analysis_jobs WHERE upload_id IN (SELECT upload_id FROM doomed);
DELETE FROM diet_uploads WHERE upload_id IN (SELECT upload_id FROM doomed);
COMMIT;
SQL
psql -c "SELECT count(*) AS remaining_uploads FROM diet_uploads;"

echo
echo "== MinIO 정리 =="
sudo docker exec "$MINIO_CONTAINER" sh -c '
  mc alias set local http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
  mc rm --recursive --force local/diet-photos/vision-qa/load- 2>/dev/null || true
  mc rm --recursive --force local/diet-photos/vision-qa/e2e- 2>/dev/null || true
  mc rm --recursive --force local/diet-photos/e2e/ 2>/dev/null || true
  echo "남은 vision-qa 프리픽스:"; mc ls local/diet-photos/vision-qa/'

echo
echo "== MongoDB 정리 =="
MONGODB_URI="$(sudo docker inspect "$CONSUMER_CONTAINER" \
  --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^MONGODB_URI=//p')"
sudo docker exec -i "$MONGO_CONTAINER" mongosh "$MONGODB_URI" --quiet --eval "
  const r = db.user_activity_events.deleteMany({ user_id: ${TEST_USER_ID} });
  print('삭제된 활동 이벤트: ' + r.deletedCount);
  print('남은 문서: ' + db.user_activity_events.countDocuments({}));"

echo
echo "정리 완료"
