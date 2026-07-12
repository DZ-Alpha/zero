#!/usr/bin/env bash
# Manual rollback for the ci-sandbox deployment on harbor VM.
# Usage: scripts/rollback.sh [image-tag]
#   - image-tag omitted: rolls back to the last known-good tag recorded by
#     the deploy job (~/ci-sandbox-state/last-good-tag).
#   - HARBOR_ROBOT_USER / HARBOR_ROBOT_TOKEN env vars are optional; if set,
#     the script logs in to Harbor before pulling. Otherwise it assumes an
#     existing docker login session (e.g. left over from a CI run).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STATE_FILE="$HOME/ci-sandbox-state/last-good-tag"
IMAGE_NAME="harbor.hizero.local/dangdang/ci-sandbox"

TAG="${1:-}"
if [ -z "$TAG" ]; then
  if [ ! -f "$STATE_FILE" ]; then
    echo "No tag given and no $STATE_FILE found. Usage: rollback.sh [image-tag]" >&2
    exit 1
  fi
  TAG="$(cat "$STATE_FILE")"
  echo "No tag given, using last known-good tag: $TAG"
fi

if [ -n "${HARBOR_ROBOT_USER:-}" ] && [ -n "${HARBOR_ROBOT_TOKEN:-}" ]; then
  echo "$HARBOR_ROBOT_TOKEN" | docker login harbor.hizero.local -u "$HARBOR_ROBOT_USER" --password-stdin
fi

IMAGE="$IMAGE_NAME:$TAG"
echo "Rolling back ci-sandbox to $IMAGE"
docker pull "$IMAGE"

cd "$REPO_ROOT/infra/ci-sandbox"
IMAGE_TAG="$TAG" docker compose up -d

echo "Verifying health..."
for i in $(seq 1 10); do
  if curl -fs http://localhost:8080/health >/dev/null; then
    echo "Rollback successful, service healthy on tag $TAG"
    echo "$TAG" > "$STATE_FILE"
    exit 0
  fi
  echo "Health check attempt $i failed, retrying in 3s..."
  sleep 3
done

echo "WARNING: rolled back to $TAG but health check is still failing. Manual investigation needed." >&2
exit 1
