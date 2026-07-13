# 모니터링 스택 (별도 VM, harbor VM과 분리)

Harbor/CI 인프라와 장애 영향을 분리하기 위해 모니터링은 별도 Proxmox VM(VMID 103,
`192.168.0.51` / Tailscale `100.110.81.51`)에서 운영한다.

구성: **Grafana Alloy가 단일 수집 지점**으로 앱에서 오는 로그/메트릭/트레이스를 OTLP로 받아
각각 Loki(로그)/Prometheus(메트릭, remote_write로 push)/Tempo(트레이스)로 나눠 보내고,
Grafana가 세 데이터소스를 조회한다. (설계도 `docker` 탭 기준, Alloy는 OpenTelemetry Collector의
Grafana Labs 배포판이라 OTLP를 그대로 받을 수 있음 — 앱 쪽 계측 코드 변경 불필요)

```
앱 --OTLP(4317/4318)--> alloy --+--> tempo                        (트레이스)
                                 +--> loki                         (로그)
                                 +--> prometheus (remote_write push) (메트릭)
                                                    |
                                                 grafana (조회)
```

## 실행

```bash
cd infra/monitoring
cp .env.example .env   # GRAFANA_ADMIN_PASSWORD를 실제 값으로 변경
docker compose up -d
```

- Grafana: `http://192.168.0.51:3000` (`admin` / `.env`에 설정한 비밀번호)
- Prometheus: `http://192.168.0.51:9090`
- 앱에서 텔레메트리 전송: `http://192.168.0.51:4317`(OTLP gRPC) 또는 `:4318`(OTLP HTTP)

## 참고

- 이미지 태그는 전부 고정(pin)했다. `:latest` 대신 명시적 버전을 써서 예기치 않은 브레이킹
  업데이트를 방지한다.
- Loki는 이미지에 기본 번들된 설정(`/etc/loki/local-config.yaml`, 단일 바이너리+로컬 파일시스템)을
  그대로 사용한다. 커스텀 설정이 필요해지면 그때 `config/`에 추가한다.
- 첫 배포 직후엔 반드시 실제 트래픽(또는 테스트 요청)으로 Prometheus 타겟 상태, Loki 로그 수신,
  Tempo 트레이스 수신을 각각 실측 검증할 것 — 설정 파일만으로는 동작을 보장할 수 없다.
