#!/usr/bin/env bash
# 부하테스트 결과 수집 — run 직후 실행하면 시방서 환산에 필요한 값을 한 번에 뽑는다.
# 눈으로 그래프 읽어 옮겨적는 과정을 없애기 위한 것(전사 실수 방지 + 재현 가능).
#
# 사용법:  ./harvest.sh <testid> <container> [window]      기본 window=2m30s
#   예:    ./harvest.sh w1-product-steady-r1 product-service
#          ./harvest.sh w1-product-ramp product-service 6m     # ramp 전체 구간
#          ./harvest.sh --names                                # k6 메트릭 이름 확인
#
# window는 "지금부터 과거로" 거슬러 보는 구간이라 run이 끝나자마자 실행해야 한다.
# steady 3m 중 워밍업 30초를 빼려고 기본값이 2m30s.
set -euo pipefail

PROM=${PROM:-http://100.110.81.51:9090}
JOB=${JOB:-cadvisor-production-vm}

q() { # PromQL 1개 → 스칼라(없으면 빈칸)
  curl -s -G "$PROM/api/v1/query" --data-urlencode "query=$1" \
    | jq -r '.data.result[0].value[1] // ""'
}

if [ "${1:-}" = "--names" ]; then
  echo "== 최근 3시간 k6 메트릭 이름 =="
  curl -s -G "$PROM/api/v1/series" --data-urlencode 'match[]={__name__=~"k6_.+"}' \
    --data-urlencode "start=$(date -d '3 hours ago' +%s)" --data-urlencode "end=$(date +%s)" \
    | jq -r '.data[].__name__' | sort -u
  exit 0
fi

TESTID=${1:?usage: harvest.sh <testid> <container> [window]}
SVC=${2:?usage: harvest.sh <testid> <container> [window]}
W=${3:-2m30s}
# window를 초로 (RPS 계산용) — 2m30s / 6m / 90s 형태 지원
WSEC=$(awk -v w="$W" 'BEGIN{s=0;n="";for(i=1;i<=length(w);i++){c=substr(w,i,1);
  if(c ~ /[0-9]/){n=n c} else {if(c=="h")s+=n*3600; else if(c=="m")s+=n*60; else s+=n; n=""}}
  if(n!="")s+=n; print s}')

echo "== $TESTID / $SVC / 최근 $W (${WSEC}s) =="

# ── k6 클라이언트 측 (SLO 판정)
# 주의 2건 (2026-07-27 실측으로 확인):
#  1) k6 remote-write는 지연을 "초" 단위로 저장한다(0.0523 = 52.3ms) → ×1000 해서 ms로 본다.
#  2) 시리즈가 엔드포인트별로 쪼개져 있다 → max()로 "최악 엔드포인트" 값을 본다.
#     전체 집계 p95는 k6 콘솔 요약(THRESHOLDS 블록)이 정답이고, 여기 값은 보수적 참고치.
P95=$(q "max(max_over_time(k6_http_req_duration_p95{testid=\"$TESTID\"}[$W]))")
P99=$(q "max(max_over_time(k6_http_req_duration_p99{testid=\"$TESTID\"}[$W]))")
FAIL=$(q "max(max_over_time(k6_http_req_failed_rate{testid=\"$TESTID\"}[$W]))")
REQS=$(q "sum(increase(k6_http_reqs_total{testid=\"$TESTID\"}[$W]))")
RPS=$(awk -v r="${REQS:-0}" -v s="$WSEC" 'BEGIN{if(s>0)printf "%.1f", r/s; else print ""}')

# ── 컨테이너 자원 (시방서 requests/limits의 원천)
# 주의: scrape_interval 15s라 1분 rate는 순간 스파이크를 평활한다 — 피크는
# 과소평가 방향이고, 그래서 limits에 ×1.5~2.0 여유를 두는 것.
CPU_AVG=$(q "avg_over_time((sum(rate(container_cpu_usage_seconds_total{job=\"$JOB\",name=\"$SVC\"}[1m])))[$W:15s])")
CPU_MAX=$(q "max_over_time((sum(rate(container_cpu_usage_seconds_total{job=\"$JOB\",name=\"$SVC\"}[1m])))[$W:15s])")
MEM_AVG=$(q "avg_over_time((sum(container_memory_working_set_bytes{job=\"$JOB\",name=\"$SVC\"}))[$W:15s])")
MEM_MAX=$(q "max_over_time((sum(container_memory_working_set_bytes{job=\"$JOB\",name=\"$SVC\"}))[$W:15s])")
MEM_LIMIT=$(q "max(container_spec_memory_limit_bytes{job=\"$JOB\",name=\"$SVC\"})")
RESTARTS=$(q "sum(changes(container_start_time_seconds{job=\"$JOB\",name=\"$SVC\"}[$W]))")

# ── 병목 귀속 (이 회차의 R이 "컨테이너 한계"가 맞는지 판정하는 근거)
GW_CPU=$(q "max_over_time((sum(rate(container_cpu_usage_seconds_total{job=\"$JOB\",name=\"b-gateway\"}[1m])))[$W:15s])")
NODE_CPU=$(q "max_over_time((100 - avg(rate(node_cpu_seconds_total{job=\"production-vm\",mode=\"idle\"}[1m]))*100)[$W:15s])")
GEN_CPU=$(q "max_over_time((100 - avg(rate(node_cpu_seconds_total{job=\"harbor-vm\",mode=\"idle\"}[1m]))*100)[$W:15s])")
DB_TOP=$(curl -s -G "$PROM/api/v1/query" --data-urlencode \
  "query=topk(3, max_over_time((sum by (name)(rate(container_cpu_usage_seconds_total{job=\"cadvisor-db-vm\",name!=\"\"}[1m])))[$W:15s]))" \
  | jq -r '.data.result[] | "\(.metric.name)=\((.value[1]|tonumber*1000|round))m"' | paste -sd' ' -)
CADV_UP=$(q "min_over_time(up{job=\"$JOB\"}[$W])")
# 업로드(대용량 multipart) 회차에서 네트워크가 먼저 포화하는지 — 1Gbps ≈ 119 MB/s
NET_RX=$(q "max_over_time((sum(rate(node_network_receive_bytes_total{job=\"production-vm\",device!~\"lo|veth.*|docker.*|br-.*\"}[1m])))[$W:15s])")

f() { [ -z "${1:-}" ] && { echo -n "n/a"; return; }; awk -v v="$1" -v m="${2:-1}" 'BEGIN{printf "%.1f", v*m}'; }
MiB=$(awk 'BEGIN{print 1/1048576}')

echo "--- SLO (k6, 초→ms 환산 / 최악 엔드포인트 기준)"
echo "  p95        : $(f "$P95" 1000) ms   (SLO 500 — 전체 집계는 k6 콘솔 요약 참조)"
echo "  p99        : $(f "$P99" 1000) ms"
echo "  err rate   : $(f "$FAIL" 100) %  (SLO 1)"
echo "  실측 RPS   : ${RPS:-n/a}"
echo "--- 컨테이너 $SVC (시방서 입력값)"
echo "  CPU  평균  : $(f "$CPU_AVG" 1000) m   → requests.cpu"
echo "  CPU  피크  : $(f "$CPU_MAX" 1000) m   → limits.cpu = 피크×1.5~2.0"
echo "  MEM  평균  : $(f "$MEM_AVG" "$MiB") MiB → requests.memory"
echo "  MEM  피크  : $(f "$MEM_MAX" "$MiB") MiB → limits.memory = 피크×1.3~1.5"
echo "  MEM  한도  : $(f "$MEM_LIMIT" "$MiB") MiB  (피크가 90%↑면 눌린 측정 — 상향 후 재측정)"
echo "  재시작     : ${RESTARTS:-0}  (0이 아니면 OOMKill 의심 → 이 회차 무효)"
echo "--- 병목 귀속 (R이 컨테이너 한계인지 판정)"
echo "  b-gateway  : $(f "$GW_CPU" 1000) m / 500m 한도   (0.45↑면 게이트웨이를 재는 중)"
echo "  production : $(f "$NODE_CPU") % node CPU"
echo "  harbor(생성): $(f "$GEN_CPU") %  (70↑면 생성기 한계 — R4)"
echo "  DB VM top  : ${DB_TOP:-n/a}"
echo "  net rx     : $(f "$NET_RX" 0.000001) MB/s  (1Gbps≈119 — 업로드 회차에서 80↑면 네트워크 병목)"
echo "  cadvisor up: ${CADV_UP:-n/a}  (1이 아니면 측정 공백 — R9)"
echo "--- 기록표 붙여넣기용 TSV"
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$SVC" "${RPS:-}" "$(f "$P95" 1000)" \
  "$(f "$CPU_AVG" 1000)m" "$(f "$CPU_MAX" 1000)m" "$(f "$MEM_AVG" "$MiB")Mi" "$(f "$MEM_MAX" "$MiB")Mi" "$TESTID"
