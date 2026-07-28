# DaemonSet

## 🟡 무엇인가

- **한 줄 정의**: 클러스터의 모든(또는 조건에 맞는 일부) 노드마다 똑같은 파드를 **정확히 1개씩** 돌게 보장하는 워크로드 컨트롤러다.

- **핵심 개념**:
  - **노드당 1개 보장**: replica 필드가 없고 **노드 수가 곧 파드 수**. 노드 추가 시 자동 생성, 제거 시 자동 회수(GC). 비유 한 줄: 건물 각 층마다 두는 소화기 — 개수가 아니라 "빠짐없이"가 목적.
  - **노드-로컬 작업용**: 노드 자신의 지표·로그·디바이스에 접근하려면 그 노드 위에 있어야 한다 → 로그/메트릭 수집기, CNI·CSI 플러그인이 전형적 사용처.
  - **일부 노드만 선택**: `nodeSelector`/`nodeAffinity`로 라벨이 맞는 노드로 좁힐 수 있다(기본은 모든 노드).
  - **기본 스케줄러가 배치(1.12+)**: 컨트롤러는 노드 지정 `nodeAffinity`만 주입하고 배치는 kube-scheduler가 수행 — 리소스 부족·우선순위·프리엠션이 적용된다.
  - **자동 톨러레이션**: `node.kubernetes.io/unschedulable:NoSchedule` 등을 자동 부여 → cordon된 노드·컨트롤플레인 노드에도 데몬이 뜬다.
  - **업데이트 전략**: `RollingUpdate`(기본, 노드별 한 번에 하나) / `OnDelete`(수동 삭제 시 교체).

- **공식문서**:
  - [DaemonSet | Kubernetes](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/) — "all (or some) Nodes run a copy of a Pod", 노드 증감 자동 추종, 1.12+ 기본 스케줄러, 자동 톨러레이션.
  - [Perform a Rolling Update on a DaemonSet](https://kubernetes.io/docs/tasks/manage-daemon/update-daemon-set/) — `RollingUpdate`/`OnDelete` 전략, 롤링 중 한 노드에 한 파드만 유지.

- **면접 포인트**:
  - **Q. Deployment replica를 노드 수만큼 주면 같지 않나?** → A. 아니다. Deployment는 같은 노드에 몰릴 수 있고 노드 증가에 자동 추종하지 않는다. DaemonSet은 "노드당 정확히 1개 + 자동 추종"을 보장.
  - **Q. DaemonSet 파드는 스케줄러를 거치나?** → A. 1.11까지는 컨트롤러가 직접 바인딩했지만 **1.12부터 기본 스케줄러가 배치**한다. "스케줄러를 안 탄다"는 옛말.
  - **Q. 컨트롤플레인 노드엔 안 뜬다?** → A. 틀림. 자동 톨러레이션 덕에 테인트·cordon 노드에도 뜰 수 있다. 빼려면 `nodeSelector`/`affinity`로 대상을 좁혀야 한다.

## 🟡 왜 우리 서비스에서?

- **node-exporter**: 호스트 레벨 지표(CPU·메모리·디스크·네트워크)는 노드마다 재야 의미 있음 → master×3 + worker×5 = 8노드에 정확히 8개. Deployment면 몰려서 관측 사각지대 발생.
- **OTel Collector Agent 계층**: Alloy를 OTel로 대체하며 **Agent(DaemonSet) + Gateway(Deployment)** 로 분리 — Agent는 노드-로컬로 로그·메트릭·트레이스를 1차 수집, 무상태 Gateway가 Loki·Tempo·Prometheus로 라우팅.
- 대비: Prometheus(중앙 pull)·kube-state-metrics(클러스터 오브젝트 상태)는 노드-로컬이 아니라 Deployment.
- **보안 충돌 관리(2026-07-26 정정)**: node-exporter·OTel Agent의 hostPath·hostNetwork는 공식 PSS상 **baseline에서도 금지** → 이 DaemonSet들만 전용 네임스페이스로 분리해 **privileged**를 최소 범위 적용(나머지 관측 스택은 restricted 유지), 대신 SecurityContext(`runAsNonRoot`, `allowPrivilegeEscalation:false`, `capabilities.drop:[ALL]`, seccomp `RuntimeDefault`) + 최소권한 RBAC으로 균형.
- CNI(Calico/Cilium) 노드 에이전트도 같은 DaemonSet 패턴 — 클러스터 전반에 일관 적용.
