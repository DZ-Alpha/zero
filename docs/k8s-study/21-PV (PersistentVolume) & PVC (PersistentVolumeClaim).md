# PV (PersistentVolume) & PVC (PersistentVolumeClaim)

## 🟡 무엇인가

- **한 줄 정의**: PV는 클러스터에 실제로 존재하는 스토리지 자원이고, PVC는 사용자가 내는 "이만큼 이런 방식으로 쓰겠다"는 요청서이며, 파드는 PV가 아닌 **PVC를 마운트**한다.
- **핵심 개념**:
  - **PV = 실제 자원 / PVC = 요청**: PV는 파드와 독립적 생명주기를 가진 클러스터 스코프 자원, PVC는 네임스페이스 스코프 요청. Pod가 노드 자원을 소비하듯 PVC는 PV를 소비한다.
  - **바인딩은 배타적 1:1**: 한 PVC는 한 PV에만 묶이고, 묶인 PV는 다른 PVC가 못 쓴다. 요청보다 큰 PV가 배정될 수는 있다(최소한 요청량 보장).
  - **파드는 PVC 참조**: `spec.volumes[].persistentVolumeClaim.claimName`으로 PVC만 지정. 이 간접 계층이 스토리지 구현과 앱을 분리한다.
  - **accessModes**: `RWO`=한 노드 읽기·쓰기 / `ROX`=여러 노드 읽기 전용 / `RWX`=여러 노드 읽기·쓰기 / `RWOP`=단 하나의 파드만. 플러그인마다 지원이 다르다.
  - **생명주기 4단계**: Provisioning(정적/동적) → Binding → Using → Reclaiming.
  - **Reclaim 정책·상태**: `Retain`(데이터 보존, 수동 정리) / `Delete`(실제 스토리지까지 삭제) / `Recycle`(폐기됨). PV phase는 Available→Bound→Released→Failed.
- **공식문서**:
  - [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) — PV/PVC 정의, 생명주기, accessModes, Reclaim 정책, phase.
  - [Dynamic Volume Provisioning](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/) — StorageClass가 PVC 요청에 맞춰 PV를 자동 생성하는 원리.
- **면접 포인트**:
  - **Q. RWO면 파드 하나만 쓸 수 있나?** → 아니다. RWO는 **노드 단위** — 같은 노드의 여러 파드는 동시 접근 가능. 파드 하나로 강제하려면 `RWOP`. 가장 자주 틀리는 지점.
  - **Q. PV와 PVC 중 네임스페이스에 속하는 건?** → **PVC만**. PV는 클러스터 스코프라 네임스페이스가 없다.
  - **Q. PVC를 지우면 데이터도 항상 지워지나?** → 아니다. `Retain`이면 PV가 Released 상태로 남아 수동 정리 필요, `Delete`일 때만 실제 스토리지까지 삭제된다.

## 🟡 왜 우리 서비스에서?

- 김지훈 담당 `dang-obsv-ns` 모니터링 스택이 최대 소비처 — 저장을 **로컬 PVC(WAL) + MinIO(장기 오브젝트)** 2단으로 설계, Prometheus·Loki·Tempo의 WAL/최근 블록은 파드 전용 PVC(RWO)에 담는다.
- Prometheus를 StatefulSet으로 올린 이유가 `volumeClaimTemplates`로 `prometheus-0` 전용 PVC를 자동 생성해 1:1로 묶기 위함.
- 물리 2호스트뿐이라 RWX 공유 파일시스템 대신 노드 전용 `RWO` 모델이 자연스럽다. (참고: persistentVolumeClaim은 PSS restricted 허용 볼륨이라 PVC 사용은 PSA 완화 사유가 아니다 — 완화는 root DB 이미지(dang-db-ns=baseline)와 hostPath·hostNetwork를 쓰는 관측 에이전트(privileged 전용 ns 분리)의 몫, 01 문서 정정 참조.)
- `dang-vault-ns` Vault의 Raft 데이터도 PVC 필수. 반대로 Grafana(provisioning+GitOps), OTel Collector Gateway, Alertmanager는 의도적 무상태 — "무엇에 PVC를 붙일지"를 컴포넌트별로 명시적으로 가른 것이 설계 핵심.
- 유실이 뼈아픈 데이터(모니터링·DB·Vault)는 `Retain`, 재생성 가능한 임시 볼륨은 `Delete`로 정책을 못박아 데이터 안전과 용량 관리를 동시에 잡는다.
