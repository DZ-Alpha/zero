# StatefulSet

## 🟡 무엇인가

- **한 줄 정의**: 각 파드에 **바뀌지 않는 고유 이름(신원)과 파드 전용 영속 볼륨**을 보장하는 상태 저장(stateful) 워크로드 컨트롤러다.

- **핵심 개념**:
  - **공식 4조건**: ① 안정적·고유한 네트워크 식별자, ② 안정적인 영속 스토리지, ③ 순서 보장 배포·스케일링, ④ 순서 보장 롤링 업데이트 — 하나라도 필요하면 StatefulSet, 아니면 Deployment.
  - **안정적 신원**: 파드 이름은 `$(statefulset name)-$(ordinal)`(0~N-1)로 고정되고, 재스케줄돼도 유지된다. 비유 한 줄: 콜센터의 "아무 상담원"(Deployment) vs 지정 좌석+개인 사물함의 "3번 창구 직원"(StatefulSet).
  - **volumeClaimTemplates**: 템플릿 1개당 파드마다 PVC가 자동 생성된다(`www` + `web-0/1/2` → `www-web-0/1/2`). 파드가 죽어도 같은 PVC에 다시 붙는다.
  - **헤드리스 서비스 필수**: 네트워크 신원용 Headless Service(`clusterIP: None`)를 **사용자가 직접** 만들어야 하며, `pod-1.svc.ns.svc.cluster.local` 같은 안정적 DNS를 제공한다.
  - **볼륨 미삭제**: StatefulSet 삭제/스케일 다운 시 PVC/PV는 **자동으로 지워지지 않는다**(기본값; v1.32 GA `persistentVolumeClaimRetentionPolicy`로 opt-in 자동 삭제 가능) — 데이터 안전이 자동 정리보다 우선.
  - **순서 보장(기본 `OrderedReady`)**: 스케일 업은 0→N-1 순, 다운·롤링 업데이트는 역순으로 하나씩.

- **공식문서**:
  - [StatefulSets (concepts)](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/) — 4조건, 이름 규칙, 헤드리스 서비스 필수, 볼륨 미삭제.
  - [StatefulSet Basics (튜토리얼)](https://kubernetes.io/docs/tutorials/stateful-application/basic-stateful-set/) — 파드 재생성 후에도 같은 PVC에 재마운트되어 데이터가 유지됨을 실습으로 확인.

- **면접 포인트**:
  - **Q. Deployment와의 스토리지 차이는?** → A. Deployment는 하나의 PVC를 여러 파드가 **공유(참조)**, StatefulSet은 `volumeClaimTemplates`로 **파드마다 전용 PVC 자동 생성**. "공유 vs 개별 소유"가 결정적 차이.
  - **Q. StatefulSet이면 자동으로 HA인가?** → A. 아니다. 신원·순서·스토리지만 보장하고, 복제·정족수·리더 선출은 애플리케이션 몫이다(예: MySQL 복제, Raft).
  - **Q. StatefulSet을 지우면 데이터도 지워지나?** → A. 아니다. PVC/PV는 남고 재배포 시 다시 붙는다. 완전 삭제는 PVC를 수동으로 지워야 한다.

## 🟡 왜 우리 서비스에서?

- `dang-obsv-ns` **Prometheus**: WAL/TSDB는 파드 전용으로 남아야 하므로 StatefulSet + `volumeClaimTemplates`로 `prometheus-0` 전용 PVC를 고정 — 재시작 시 같은 WAL을 이어받아 수집 공백·유실 방지. (참고: persistentVolumeClaim은 PSS restricted 허용 볼륨이라 PVC 사용 자체는 PSA 완화 사유가 아니다 — 01 문서 정정 참조.)
- **Alertmanager=3 결정**: gossip 클러스터는 피어를 안정적 이름(`alertmanager-0/1/2` + 헤드리스 DNS)으로 찾아야 성립 — gossip이라 물리 2호스트에서도 HA 유효(Raft인 Vault와 대비).
- `dang-vault-ns` **Vault**: Raft는 노드별 전용 데이터 디렉터리 + 안정적 DNS 조인이 필요해 StatefulSet. 다만 물리 2호스트라 정족수 3 불가 → PoC로 **replica 1** 고정, 구조만 올바로 잡음.
- **결정 트리**: 파드마다 다른 디스크가 필요하거나 피어를 이름으로 찾으면 StatefulSet(Prometheus·Loki·Tempo·Alertmanager·Vault·MinIO, `dang-db-ns` DB), 아무 파드나 같아도 되면 Deployment(Grafana·OTel Gateway).
- 이 구분이 PV/PVC 설계로 이어진다 — `volumeClaimTemplates`가 찍어낸 파드별 PVC가 로컬 PVC·MinIO 백엔드에 바인딩된다.
