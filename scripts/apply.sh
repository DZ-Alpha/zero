#!/usr/bin/env bash
# AlphaCar 매니페스트 순서 적용 헬퍼
# 사용법: bash scripts/apply.sh [--dry-run]
set -euo pipefail
cd "$(dirname "$0")/.."
DRY=""
[[ "${1:-}" == "--dry-run" ]] && DRY="--dry-run=client"

echo ">> 1. 클러스터 스코프: Namespace / ResourceQuota / LimitRange"
kubectl apply $DRY -f manifests/00-cluster/

# 네임스페이스 내부 리소스: configmap/secret/rbac -> workloads -> service/hpa/netpol/storage 순
for ns in manifests/*/; do
  base=$(basename "$ns")
  [[ "$base" == "00-cluster" ]] && continue
  echo ">> 2. $base"
  for kind in configmaps secrets rbac storage workloads services hpa networkpolicy job-* cronjob-*; do
    for f in "$ns"$kind.yaml; do
      [[ -e "$f" ]] && kubectl apply $DRY -f "$f"
    done
  done
done
echo ">> 완료. (Secret 값을 REPLACE_ME 그대로 두지 말 것 — REVIEW.md 참고)"
