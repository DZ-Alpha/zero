#!/usr/bin/env bash
#
# DAST ZAP active scan 러너 (서비스별, Harbor VM에서 실행).
#
# 무엇: 한 서비스의 openapi를 import해 ZAP active scan(zap-api-scan.py)을 인증 상태로
#   돌린다. SQLi/XSS/인젝션 등 ZAP 탐지 가능 취약점을 전 엔드포인트에 자동 주입.
#
# 한계(정직히): ZAP은 IDOR/인증·인가 로직/비즈니스 로직은 못 잡는다. 그건 별도 수동 검증.
#   여기서 "High 0"은 "주입형·설정형 공격 방어 확인"이지 "전부 안전"이 아니다.
#
# ⚠️ 안전: staging 격리 서비스만(운영 DB 아님, 사전 확인됨). active scan은 파괴적일 수
#   있으나 대상이 격리 staging PG라 안전. 토큰은 짧은 만료(3h) staging 전용.
#
# 실행(Harbor VM, docker 있음): 토큰은 mgmt에서 발급해 TOKEN env로 넘긴다.
#   TOKEN='<mgmt발급 JWT>' ./scripts/dast-zap-scan.sh <svc> <nodePort> [nodeIP]
#   예) TOKEN=... ./scripts/dast-zap-scan.sh main-service 31001
set -euo pipefail

SVC="${1:?서비스명 (예: main-service)}"
PORT="${2:?NodePort (예: 31001)}"
IP="${3:-192.168.0.71}"
TOKEN="${TOKEN:?mgmt에서 발급한 JWT를 TOKEN env로 넘기세요}"
OUT="${OUT:-$HOME/dast-scan}"
mkdir -p "$OUT" && chmod 777 "$OUT"

echo "== ZAP active scan: $SVC ($IP:$PORT) =="

# openapi 도달 확인
CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://$IP:$PORT/openapi.json" || echo "000")
if [ "$CODE" != "200" ]; then
  echo "  중단: $SVC openapi 도달 불가(status=$CODE). IP/포트/파드 상태 확인."
  exit 1
fi

# zap-api-scan.py: openapi import + active scan. Bearer 주입(replacer). -I=경고 무시(실증용).
timeout 1800 docker run --rm -v "$OUT:/zap/wrk/:rw" \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-api-scan.py \
  -t "http://$IP:$PORT/openapi.json" \
  -f openapi \
  -z "-config replacer.full_list(0).description=auth \
      -config replacer.full_list(0).enabled=true \
      -config replacer.full_list(0).matchtype=REQ_HEADER \
      -config replacer.full_list(0).matchstr=Authorization \
      -config replacer.full_list(0).replacement=Bearer\\ $TOKEN" \
  -r "$SVC.html" -J "$SVC.json" -I 2>&1 | tee "$OUT/$SVC.log" | tail -8

echo "== $SVC 완료. 리포트: $OUT/$SVC.{html,json,log} =="
# 요약 라인(Imported URLs / FAIL·WARN·PASS 카운트)만 추출.
grep -E 'Imported URLs|Total of|FAIL-NEW' "$OUT/$SVC.log" | tail -5 || true
