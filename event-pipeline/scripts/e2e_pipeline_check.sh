#!/usr/bin/env bash
# Synthetic end-to-end check for the vision and activity pipelines.
# Run on the pipeline host (zero-db). Requires sudo docker access only.
set -euo pipefail

API_CONTAINER="${API_CONTAINER:-dangdang-pipeline-api}"
CONSUMER_CONTAINER="${CONSUMER_CONTAINER:-dangdang-activity-mongodb-consumer}"
MONGO_CONTAINER="${MONGO_CONTAINER:-zero-mongodb}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONGO_WAIT_SECONDS="${MONGO_WAIT_SECONDS:-30}"

sudo docker cp "${SCRIPT_DIR}/e2e_pipeline_check.py" "${API_CONTAINER}:/tmp/e2e_pipeline_check.py"

set +e
OUTPUT="$(sudo docker exec "${API_CONTAINER}" python /tmp/e2e_pipeline_check.py 2>&1)"
VISION_RC=$?
set -e
printf '%s\n' "$OUTPUT" | grep -v '^E2E_SUMMARY '

SUMMARY="$(printf '%s\n' "$OUTPUT" | sed -n 's/^E2E_SUMMARY //p')"
if [ -z "$SUMMARY" ]; then
  echo "harness produced no summary; aborting before the MongoDB assertions" >&2
  exit 1
fi

echo
echo "== 3. MongoDB 적재 확인 =="
MONGODB_URI="$(sudo docker inspect "${CONSUMER_CONTAINER}" \
  --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^MONGODB_URI=//p')"

MONGO_RC=0
sudo docker exec -i "${MONGO_CONTAINER}" mongosh "$MONGODB_URI" --quiet --eval "
const summary = $SUMMARY;
const ids = summary.activity.event_ids;
const deadline = Date.now() + ${MONGO_WAIT_SECONDS} * 1000;
let docs = [];
while (Date.now() < deadline) {
  docs = db.user_activity_events.find({ _id: { \$in: ids } }).toArray();
  if (docs.length === ids.length) break;
  sleep(1000);
}
const report = (name, ok, detail) =>
  print('  [' + (ok ? 'PASS' : 'FAIL') + '] ' + name + (detail ? ' — ' + detail : ''));

let failures = 0;
const assert = (name, ok, detail) => { if (!ok) failures++; report(name, ok, detail); };

assert('발행한 활동 이벤트가 MongoDB 에 적재', docs.length === ids.length,
       docs.length + '/' + ids.length + ' documents');
assert('중복 발행 이벤트가 1건만 저장 (idempotency)',
       db.user_activity_events.countDocuments({ _id: summary.activity.duplicated }) === 1,
       'event_id=' + summary.activity.duplicated);
assert('_id 가 Kafka event_id 와 동일', docs.every(d => ids.includes(d._id)));
assert('user_id 가 정수 public.users.id', docs.every(d => typeof d.user_id === 'number'),
       'user_id=' + summary.activity.user_id);
assert('producer 가 서비스명 형식', docs.every(d => /-service\$/.test(d.producer)));
assert('event_type 이 user. 네임스페이스', docs.every(d => d.event_type.startsWith('user.')));
// Key names only: a value such as {\"method\": \"password\"} is not a leak.
const banned = ['email', 'password', 'jwt', 'token', 'access_token', 'birth_year',
                'height_cm', 'weight_kg', 'image_key', 'image_url'];
const keysOf = (value) => {
  if (Array.isArray(value)) return value.flatMap(keysOf);
  if (value && typeof value === 'object')
    return Object.keys(value).concat(Object.values(value).flatMap(keysOf));
  return [];
};
const leaked = docs.flatMap(d => keysOf(d).filter(k => banned.includes(k)));
assert('개인정보/이미지 키가 payload 에 없음', leaked.length === 0, leaked.join(','));

print('');
print(failures === 0
  ? '  MongoDB 검사 통과'
  : '  MongoDB 검사 실패 ' + failures + '건');
quit(failures === 0 ? 0 : 1);
" || MONGO_RC=$?

echo
if [ "$VISION_RC" -eq 0 ] && [ "$MONGO_RC" -eq 0 ]; then
  echo "두 파이프라인 전체 통과"
  exit 0
fi
echo "실패한 검사가 있습니다 (vision_rc=${VISION_RC} mongo_rc=${MONGO_RC})"
exit 1
