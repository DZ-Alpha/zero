# StorageClass

## 🟡 무엇인가

- **한 줄 정의**: StorageClass는 "이런 성격의 스토리지를 만들어 달라"는 주문서(템플릿)로, PVC가 이를 참조하면 provisioner가 PV를 **동적으로 자동 생성**해 바인딩한다.
- **핵심 개념**:
  - **provisioner**: 실제 볼륨을 만드는 CSI 드라이버 지정. Longhorn은 `driver.longhorn.io`. StorageClass는 규칙일 뿐, 실제 생성은 이 드라이버가 한다.
  - **parameters**: 프로비저너 세부 옵션. Longhorn은 `numberOfReplicas`(기본 "3"), `staleReplicaTimeout`(기본 "2880"분), `dataLocality`, `fsType` 등.
  - **reclaimPolicy**: 동적 생성 PV의 PVC 삭제 시 처리. 기본값 `Delete`(실제 볼륨까지 삭제), `Retain`은 보존 후 수동 회수.
  - **volumeBindingMode**: `Immediate`(기본, PVC 생성 즉시 프로비저닝) vs `WaitForFirstConsumer`(Pod 스케줄까지 지연 → 볼륨을 Pod와 같은 노드/존에 배치).
  - **allowVolumeExpansion**: `true`면 PVC 용량 온라인 확장 가능.
  - **default StorageClass**: `is-default-class: "true"` 애너테이션 클래스가 `storageClassName` 생략 시 자동 적용. 클러스터당 1개만 두는 게 안전.
- **공식문서**:
  - [Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/) — provisioner/parameters/reclaimPolicy 필드, 기본값(Delete, Immediate).
  - [Dynamic Volume Provisioning](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/) — PVC가 StorageClass를 참조하면 관리자가 PV를 미리 만들 필요 없이 자동 프로비저닝.
- **면접 포인트**:
  - **Q. PV, PVC, StorageClass 관계는?** → PVC는 요청서, PV는 실제 볼륨, StorageClass는 PV를 자동으로 찍어내는 공장 설정. PVC가 클래스를 참조하면 PV가 동적 생성·바인딩된다.
  - **Q. reclaimPolicy 기본값은?** → 동적 생성 PV는 **Delete**(정적 PV 기본은 Retain이라 헷갈림). 지워지면 안 되는 데이터는 Retain 명시 필수.
  - **Q. Immediate vs WaitForFirstConsumer?** → Immediate는 볼륨 위치가 먼저 고정돼 Pod가 다른 노드/존에 뜨면 붙지 못할 수 있다. WFC는 Pod 스케줄 위치에 맞춰 볼륨을 만들어 이를 피한다. 토폴로지 중요한 로컬/존 스토리지에 권장.

## 🟡 왜 우리 서비스에서?

- worker 5대에서 Pod 위치를 미리 알 수 없어 정적 PV 대신 **Longhorn CSI(`driver.longhorn.io`) StorageClass 동적 프로비저닝** 채택. Longhorn 복제로 한 노드가 죽어도 데이터 생존.
- 최대 소비자는 내 담당 `dang-obsv-ns` — "로컬 PVC(WAL) + MinIO(장기)" 2단이라 WAL PVC는 `Delete`, 유실 불가한 `dang-vault-ns` Vault Raft는 `Retain` 클래스로 분리. "성격별로 클래스를 나눈다"가 우리 결정.
- `numberOfReplicas`는 물리 2호스트 한계와 얽힌다 — 복제 3개여도 물리 분산이 안 되며, Vault replica 1(PoC) 결정("Raft 정족수 3은 물리 3호스트 필요")과 같은 맥락.
- `volumeBindingMode: WaitForFirstConsumer` 우선 — `dang-be-ns` 등 Pod 스케줄 위치에 맞춰 볼륨을 만들어 `dataLocality`를 살리고 볼륨-Pod 어긋남 방지.
- 정리: StorageClass는 보존 정책(Delete/Retain)·복제 전략·배치 전략을 네임스페이스 성격별로 코드화하는 지점이다.
