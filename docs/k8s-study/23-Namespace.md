# Namespace

## 🟡 무엇인가
- **한 줄 정의**: 하나의 클러스터 안을 이름으로 구획해 여러 팀·용도가 리소스를 논리적으로 나눠 쓰게 하는 오브젝트다.
- **핵심 개념**:
  - **이름 스코프**: 오브젝트 이름은 같은 네임스페이스 안에서만 유일하면 된다. `dang-be-ns`의 `Service/api`와 `dang-fe-ns`의 `Service/api`는 다른 오브젝트.
  - **네임스페이스 스코프 vs 클러스터 스코프**: Pod·Service·Deployment·PVC 등은 네임스페이스 소속, Node·PV·StorageClass·ClusterRole·Namespace 자체는 클러스터 스코프(`kubectl api-resources --namespaced=false`).
  - **정책의 경계**: RBAC, ResourceQuota, LimitRange, NetworkPolicy, Pod Security Admission이 모두 네임스페이스 단위로 적용된다.
  - **DNS 자동 구성**: Service는 `<서비스명>.<네임스페이스>.svc.cluster.local` DNS를 얻는다. 같은 네임스페이스면 짧은 이름, 다르면 `api.dang-be-ns`.
  - **소프트 격리**: 그 자체로는 네트워크·커널·자원을 차단하지 않는다. 공식 문서도 "네임스페이스 간 보안을 강제하지 않는다"고 명시. 강한 격리는 정책을 얹거나 클러스터 분리.
  - **삭제 파급**: 네임스페이스 삭제 시 내부 모든 오브젝트가 함께 삭제(cascade)되며 되돌릴 수 없다.
- **공식문서**:
  - [Namespaces | Kubernetes](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/) — 단일 클러스터 내 리소스 그룹 격리 메커니즘, 이름은 네임스페이스 안에서만 유일.
  - [Multi-tenancy | Kubernetes](https://kubernetes.io/docs/concepts/security/multi-tenancy/) — 네임스페이스 간 보안은 강제되지 않으며, "궁극의 네임스페이스는 별도의 클러스터".
- **면접 포인트**:
  - **Q. 네임스페이스는 보안 경계인가?** → 아니다. 소프트 격리일 뿐, 기본 상태에선 타 네임스페이스 파드로 네트워크 접근이 가능하다. RBAC+NetworkPolicy+PSA+Quota를 얹거나 클러스터 분리가 필요.
  - **Q. 모든 오브젝트가 네임스페이스에 속하나?** → 아니다. Node·PV·StorageClass·ClusterRole 등은 클러스터 스코프. "PV는 클러스터, PVC는 네임스페이스"가 단골 함정.
  - **Q. 네임스페이스만 나누면 자원이 격리되나?** → 아니다. ResourceQuota·LimitRange를 명시적으로 걸어야 한다. 네임스페이스는 "정책을 걸 자리"만 제공.

## 🟡 왜 우리 서비스에서?
- 단일 클러스터(물리 호스트 2대, master×3·worker×5)를 용도별로 구획: `dang-fe-ns`·`dang-be-ns`·`dang-ai-ns`·`dang-db-ns`(앱·데이터), `dang-obsv-ns`(관측), `dang-vault-ns`·`dang-cert-manager-ns`·`dang-kyverno-ns`·`dang-sealed-secrets-ns`(보안 스택) — 공식 문서의 "신뢰 도메인 내 조직화" 용법 그대로.
- 폴더가 아니라 **정책 경계**로 사용: PSA는 원칙 `restricted`, `dang-db-ns`만 `baseline`(root DB 이미지), hostPath·hostNetwork가 필요한 관측 에이전트 DaemonSet은 전용 ns 분리 후 `privileged`(hostPath는 baseline도 금지 — 01 문서 정정).
- 소프트 격리의 한계를 알기에 **NetworkPolicy default-deny 3계층**으로 fe→be→db 방향만 열고 기본 차단, RBAC는 네임스페이스별 Role로 최소권한.
- 네임스페이스 경계는 폭발 반경(blast radius)의 1차 방어선 — 예: `dang-obsv-ns`에 ResourceQuota를 걸어 Prometheus가 다른 워크로드를 굶기지 못하게.
- 향후 하드 격리(규정·적대적 멀티테넌시)가 필요하면 별도 클러스터로 가야 함을 팀이 인지 — 현 단계(부트캠프 이관·PoC)는 단일 클러스터+정책 계층이 합리적 균형.
