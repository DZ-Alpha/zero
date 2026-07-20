#!/usr/bin/env bash
# 2026-07-20, 실무기준 점검 갭 #4 "모니터링 데이터 백업 전무" 해소.
# 매일 04:00(cron) 실행: 4개 데이터 볼륨을 컨테이너별 stop -> tar -> start로
# 정합성 있게 백업(총 ~2분 관측 공백, 새벽 저트래픽 시간대 트레이드오프 수용).
# Prometheus 공식 스냅샷 API(--web.enable-admin-api) 방식은 delete_series 등
# 파괴적 admin 엔드포인트까지 함께 열려(9090이 LAN/Tailscale 노출 중) 보안상
# 배제하고, 공식적으로도 안전한 "정지 후 데이터 디렉터리 복사"를 채택.
# 보관: 로컬 7일 로테이션 + harbor VM(100.96.79.73)으로 오프-VM 사본.
set -euo pipefail

TS=$(date +%Y%m%d-%H%M%S)
DEST=/home/bruce/monitoring-backups/$TS
KEEP_DAYS=7
OFFSITE=bruce@100.96.79.73:/home/bruce/monitoring-backups-offsite/
LOG=/home/bruce/monitoring-backups/backup.log

mkdir -p "$DEST"
exec >>"$LOG" 2>&1
echo "=== backup start $TS ==="

# 서비스: 컨테이너명=볼륨명 매핑 (docker volume은 monitoring_ 접두)
declare -A VOLS=(
  [prometheus]=monitoring_prometheus_data
  [loki]=monitoring_loki_data
  [tempo]=monitoring_tempo_data
  [grafana]=monitoring_grafana_data
)

for c in prometheus loki tempo grafana; do
  v=${VOLS[$c]}
  echo "[$c] stop -> tar $v"
  docker stop "$c" >/dev/null
  docker run --rm -v "$v":/data:ro -v "$DEST":/backup alpine \
    tar -czf "/backup/$v.tar.gz" -C /data .
  docker start "$c" >/dev/null
  echo "[$c] done ($(du -h "$DEST/$v.tar.gz" | cut -f1))"
done

# 설정/대시보드(재해복구 소스는 git에도 있지만 로컬 사본 동봉)
tar -czf "$DEST/config-and-dashboards.tar.gz" \
  -C /home/bruce/monitoring config dashboards docker-compose.yml

# 로컬 로테이션
find /home/bruce/monitoring-backups -maxdepth 1 -type d \
  -name "20*" -mtime +$KEEP_DAYS -exec rm -rf {} +

# 오프-VM 사본 (harbor VM) - 실패해도 로컬 백업은 유효하므로 경고만
if scp -q -r "$DEST" "$OFFSITE" 2>/dev/null; then
  echo "offsite copy ok"
else
  echo "WARN: offsite copy failed (local backup still valid)"
fi

echo "=== backup end $(date +%H:%M:%S) ==="
