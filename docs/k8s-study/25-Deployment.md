# Deployment

## 🟡 무엇인가
- **한 줄 정의**: Deployment는 똑같은 파드를 원하는 개수(replica)만큼 유지하고, 새 버전을 무중단(롤링 업데이트)으로 배포·롤백해주는 무상태(stateless) 워크로드 컨트롤러다.
- **핵심 개념**:
  - **선언적 관리**: "원하는 상태(desired state)"만 적으면 컨트롤러가 현재 상태를 계속 그쪽으로 수렴(reconcile)시킨다. `kubectl apply`로 관리.
  - **3계층 구조**: Deployment → ReplicaSet → Pod. RS가 "N개 유지"를 담당하고, Deployment는 리비전마다 새 RS를 만들어 버전 관리를 얹는다.
  - **롤링 업데이트**: `spec.template` 변경 시 새 RS를 서서히 키우고 옛 RS를 줄여 무중단 교체. `maxSurge`/`maxUnavailable`(기본 각 25%)로 속도·안전성 조절. 전략은 `RollingUpdate`(기본)와 `Recreate`.
  - **롤백**: 이전 RS가 리비전 히스토리로 남아 `kubectl rollout undo`로 복원. 보존 개수는 `revisionHistoryLimit`(기본 10).
  - **무상태 전제**: 파드가 서로 대체 가능(fungible)해야 한다. 파드별 고유 ID·순서·전용 스토리지가 필요하면 StatefulSet.
  - **스토리지는 참조만**: PVC를 자동 생성하지 않고 `claimName`으로 기존 PVC를 참조할 뿐. replica 여러 개가 하나의 PVC를 공유하므로 RWX가 아니면 사실상 replica=1.
- **공식문서**:
  - [Deployments | Kubernetes](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) — 무상태 워크로드 관리, 롤링 업데이트로 새 RS 확장·옛 RS 축소, `revisionHistoryLimit` 기본 10.
  - [StatefulSets | Kubernetes](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/) — 안정적 네트워크 ID·순서·파드별 스토리지가 필요하면 StatefulSet(대비용).
- **면접 포인트**:
  - **Q. Deployment vs ReplicaSet?** → RS는 "N개 유지"만, Deployment는 그 위에 버전 관리(롤링 업데이트·롤백)를 얹은 것. 실무에서 RS를 직접 안 만드는 이유.
  - **Q. Deployment vs StatefulSet?** → 파드가 대체 가능(무상태)이면 Deployment, 고유 ID·순서·전용 스토리지가 필요하면 StatefulSet. 웹/API는 Deployment, DB/메시지큐는 StatefulSet.
  - **Q. Deployment가 PVC를 만들어주나?** → 아니다. 기존 PVC를 참조만 한다. 파드별 볼륨 자동 생성은 StatefulSet의 `volumeClaimTemplates` 기능. 롤백(`rollout undo`)도 스펙만 되돌릴 뿐 데이터는 무관.

## 🟡 왜 우리 서비스에서?
- 상태를 남기지 않는 워크로드는 전부 Deployment: `dang-fe-ns` 프론트, `dang-be-ns` 백엔드 API, `dang-ai-ns` AI 추론/리뷰. 상태는 파드 밖(DB·오브젝트 스토리지)에 두는 12-factor 원칙과 맞물림.
- 롤링 업데이트로 사용자 접속 주소(192.168.0.56:3001 → production frontend) 트래픽을 배포 중에도 무중단 유지. worker 노드가 8Gi/2CPU로 작아 `maxSurge` 과다 설정 주의, requests/limits는 도커 실측 + 노드 용량 상한으로 설정.
- 모니터링·보안도 같은 기준: `dang-obsv-ns`의 Grafana(프로비저닝+SQLite로 무상태화), OTel Gateway, kube-state-metrics, `dang-cert-manager-ns`/`dang-kyverno-ns` 컨트롤러, `dang-vault-ns` Vault(PoC라 replica 1)는 Deployment.
- 반대편 경계: 노드마다 하나씩인 node-exporter·OTel Agent는 DaemonSet(→ 20-daemonset.md), 파드별 전용 볼륨·고정 ID가 필요한 `dang-db-ns`는 StatefulSet 영역.
- PVC를 참조하는 Deployment는 접근 모드 충돌 때문에 사실상 replica=1 — 배포 리뷰에서 항상 확인하는 항목.
