# Role

## 🟡 무엇인가

- **한 줄 정의**: Role은 **하나의 네임스페이스 안**에서 "어떤 리소스에 어떤 동작을 허용할지"를 모아 놓은 권한 묶음(허용 규칙 목록)이다.

- **핵심 개념**:
  - **네임스페이스 종속**: 항상 특정 네임스페이스(`metadata.namespace`)에 속하며, 그 안의 리소스에만 권한 부여 가능. Node·PV 같은 클러스터 전역 리소스는 범위 밖(→ ClusterRole).
  - **규칙 = apiGroups + resources + verbs**: 세 요소가 모두 매칭돼야 허용. 빈 문자열 `""`은 코어 그룹(pods, services, configmaps, secrets 등), 전체는 `*`.
  - **verbs**: 읽기(`get`/`list`/`watch`)와 쓰기(`create`/`update`/`patch`/`delete`) 계열. `list`는 객체 내용까지 노출되므로 `get`과 별개로 신중히.
  - **허용만 있고 거부 없음(default deny)**: 명시적으로 허용한 것 외에는 전부 거부. 규칙은 누적(additive)이라 한 번 열면 다른 규칙으로 좁힐 수 없다 → 처음부터 좁게.
  - **자체로는 무력, RoleBinding 필수**: Role은 권한의 "내용물"만 정의. RoleBinding으로 주체(사용자·그룹·ServiceAccount)에 연결해야 효력. RoleBinding은 ClusterRole도 참조 가능(그 네임스페이스로 범위 축소).

- **공식문서**:
  - <https://kubernetes.io/docs/reference/access-authn-authz/rbac/> — Role은 네임스페이스 내 역할 정의, 규칙은 apiGroups·resources·verbs 구성.
  - <https://kubernetes.io/docs/concepts/security/rbac-good-practices/> — 최소 권한 원칙, `list`/`watch`의 위험성, 와일드카드 지양.

- **면접 포인트**:
  - **Q. Role vs RoleBinding?** → Role은 "무엇을 할 수 있는가", RoleBinding은 "누구에게 주는가". 둘 다 있어야 작동.
  - **Q. Role로 Node·PV 권한 가능?** → 불가. non-namespaced 리소스는 ClusterRole 영역.
  - **Q. RBAC로 특정 리소스만 금지 가능?** → 불가. RBAC는 허용만 있고 deny 규칙이 없다. 넓게 허용 후 일부 빼는 방식 불가능. (흔한 오해: `""` = 모든 그룹 아님, **코어 그룹만**)

## 🟡 왜 우리 서비스에서?

- `dang-be-ns`·`dang-fe-ns`·`dang-ai-ns`·`dang-db-ns` 등 네임스페이스 경계를 **API 권한에도 그대로 반영**하는 도구. 예: 백엔드 파드는 자기 네임스페이스의 `configmaps`·`secrets`에 `get/list/watch`만 주는 Role 하나로 충분.
- 시크릿 2계층(Sealed Secrets + Vault + etcd 암호화) 운영에서, `dang-fe-ns` SA가 `dang-db-ns` Secret을 못 읽게 막는 **네임스페이스 가둠**이 핵심 — NetworkPolicy default-deny(fe→be→db) 격리를 API 권한 차원에서 한 겹 더 보장.
- `dang-obsv-ns` 안에서만 도는 컴포넌트(Grafana provisioning+SQLite 무상태 결정과 맞물림)는 Role로 충분. 반면 Prometheus·kube-state-metrics처럼 전 네임스페이스·Node를 훑는 것은 ClusterRole 필요 — 이 경계가 판단 기준(→ 06-ClusterRole.md).
- 원칙: **네임스페이스 안에서 끝나는 일에는 전역 권한 금지.** Role+RoleBinding으로 좁게 시작, ClusterRole은 소수 예외만.
