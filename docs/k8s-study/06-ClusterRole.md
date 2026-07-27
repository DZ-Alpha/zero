# ClusterRole

## 🟡 무엇인가

- **한 줄 정의**: ClusterRole은 네임스페이스 경계가 없는 권한 묶음으로, non-namespaced 리소스(Node, PV 등)·여러 네임스페이스 횡단 권한·리소스가 아닌 URL(`/metrics` 등)까지 다룬다.

- **핵심 개념**:
  - **namespace 필드 없음**: Node·PersistentVolume·Namespace·StorageClass 같은 **cluster-scoped 리소스**는 오직 ClusterRole로만 권한 부여 가능.
  - **바인딩에 따른 이중 성격**: ClusterRoleBinding으로 묶으면 클러스터 전역, **RoleBinding으로 묶으면 그 네임스페이스로만 축소** — 공용 권한 템플릿으로 재사용 가능.
  - **nonResourceURLs (ClusterRole 전용)**: `/healthz`·`/metrics` 같은 URL 경로 권한은 ClusterRole에서만. 한 규칙은 `resources` 또는 `nonResourceURLs` 중 하나만.
  - **기본 제공 롤**: `cluster-admin`·`admin`·`edit`·`view`. `cluster-admin`은 사실상 루트라 부여 극도로 주의.
  - **집계(aggregation)**: `aggregationRule`+라벨로 작은 ClusterRole들을 자동 합성(커스텀 리소스를 admin/edit/view에 얹을 때).
  - **규칙 문법은 Role과 동일**(apiGroups·resources·verbs). 차이는 범위와 non-namespaced/nonResourceURLs 지원뿐.

- **공식문서**:
  - <https://kubernetes.io/docs/reference/access-authn-authz/rbac/> — Node는 cluster-scoped라 ClusterRole+ClusterRoleBinding 필요, nonResourceURLs는 ClusterRole 전용, RoleBinding 참조 시 네임스페이스 한정.
  - <https://prometheus-operator.dev/docs/platform/rbac/> — Prometheus용 ClusterRole 예시: `nodes`·`nodes/metrics`·`services`·`endpoints`·`pods`에 `get/list/watch`, `nonResourceURLs: ["/metrics"]`에 `get`.

- **면접 포인트**:
  - **Q. Role vs ClusterRole의 가장 큰 차이?** → 범위. Role은 한 네임스페이스, ClusterRole은 전역 + non-namespaced 리소스 + nonResourceURLs.
  - **Q. ClusterRole을 만들면 무조건 전역인가?** → 아니다. ClusterRoleBinding이어야 전역이고, RoleBinding으로 묶으면 그 네임스페이스로만 좁혀진다. 가장 자주 틀리는 지점.
  - **Q. Prometheus·kube-state-metrics는 왜 ClusterRole 필수?** → 전 네임스페이스의 Pod/Service/Endpoints 디스커버리 + non-namespaced인 Node 메트릭 + `/metrics` nonResourceURLs 접근이 필요해 Role로는 불가능. (흔한 오해: `cluster-admin` 붙이면 편하다 → 최소권한 위배, 좁은 ClusterRole을 따로 만들 것)

## 🟡 왜 우리 서비스에서?

- **모니터링 스택이 대표 사례**: Prometheus는 전 네임스페이스(`dang-be-ns`·`dang-fe-ns`·`dang-ai-ns`·`dang-db-ns`·`dang-obsv-ns` 등)의 Pod/Service/Endpoints를 디스커버리하고 워커 노드(worker×5)의 node-exporter·kubelet/cAdvisor를 긁는다. kube-state-metrics도 클러스터 전 오브젝트 상태를 읽는다 → 둘 다 ClusterRole 필수.
- 단, **읽기 전용 좁은 ClusterRole**로: 필요한 리소스에 `get/list/watch`, `nonResourceURLs: ["/metrics"]`에 `get`만. `create`/`delete` 계열 배제 — SecurityContext(runAsNonRoot 등)·PSA restricted와 같은 "필요한 만큼만" 기조.
- **보안 스택**도 태생적으로 전역: Kyverno(전 워크로드 검증·변형), cert-manager(여러 네임스페이스 Certificate + ClusterIssuer), Sealed Secrets 컨트롤러(전역 복호화).
- 원칙: **전역이 꼭 필요한 소수에게만 ClusterRole**, 일반 워크로드는 Role로 가둠(→ 05-Role.md). 여러 네임스페이스에서 반복되는 권한 패턴은 ClusterRole 하나 정의 후 각 네임스페이스에 RoleBinding으로 좁게 재사용 — 정의는 한 곳, 노출은 최소, GitOps 관리도 깔끔.
