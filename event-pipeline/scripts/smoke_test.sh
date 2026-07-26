#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:18080}"
USER_TOKEN="e2e-user-token"
OBJECT_KEY="e2e/$(date -u +%Y%m%dT%H%M%SZ)-$$.png"
IMAGE_REF="minio://diet-photos/${OBJECT_KEY}"
PNG_B64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="

docker exec -e E2E_OBJECT_KEY="$OBJECT_KEY" -e E2E_PNG_B64="$PNG_B64" dangdang-pipeline-api \
  python -c 'import base64,io,os; from minio import Minio; c=Minio(os.environ["MINIO_ENDPOINT"],access_key=os.environ["MINIO_ACCESS_KEY"],secret_key=os.environ["MINIO_SECRET_KEY"],secure=False); b=base64.b64decode(os.environ["E2E_PNG_B64"]); c.put_object(os.environ["MINIO_BUCKET"],os.environ["E2E_OBJECT_KEY"],io.BytesIO(b),len(b),content_type="image/png")'

UPLOAD_RESPONSE="$(curl --fail --silent -X POST \
  -H 'Content-Type: application/json' \
  --data "{\"img\":\"${IMAGE_REF}\",\"mode\":\"daily\"}" \
  "${API_URL}/b/diet/upload?usr=${USER_TOKEN}")"
UPLOAD_ID="$(printf '%s' "$UPLOAD_RESPONSE" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')"
test -n "$UPLOAD_ID"

ANALYZE_RESPONSE="$(curl --fail --silent -X POST \
  -H 'Content-Type: application/json' \
  --data "{\"img\":\"${IMAGE_REF}\"}" \
  "${API_URL}/b/diet/ai-analyze?usr=${USER_TOKEN}")"
ANALYSIS_ID="$(printf '%s' "$ANALYZE_RESPONSE" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')"
test -n "$ANALYSIS_ID"

for _ in $(seq 1 30); do
  RESULT="$(curl --silent "${API_URL}/b/diet/ai-analyze?id=${ANALYSIS_ID}&usr=${USER_TOKEN}")"
  case "$RESULT" in
    *'"status":"DONE"'*'"list-diet"'*)
      OTHER="$(curl --fail --silent "${API_URL}/b/diet/other-foods?id=${ANALYSIS_ID}&usr=${USER_TOKEN}")"
      printf '%s\n' "$RESULT"
      printf '%s\n' "$OTHER"
      exit 0
      ;;
    *'"status":"FAILED"'*) printf '%s\n' "$RESULT" >&2; exit 1 ;;
  esac
  sleep 1
done

echo "analysis did not complete within 30 seconds: ${ANALYSIS_ID}" >&2
exit 1
