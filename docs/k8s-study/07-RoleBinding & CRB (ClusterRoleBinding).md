# RoleBinding & CRB (ClusterRoleBinding)

## 🟡 무엇인가
- **한 줄 정의**: RoleBinding/ClusterRoleBinding은 권한 묶음(Role/ClusterRole)을 대상(ServiceAccount·User·Group)에게 연결하는 오브젝트다 — 권한 자체가 아니라 배선(wiring).
- **핵심 개념**:
  - **바인딩은 권한을 담지 않는다**: `roleRef`로 Role/ClusterRole을 참조만 하고, 규칙은 Role 쪽에. 대상은 `subjects`.
  - **RoleBinding** = 네임스페이스 범위 부여. Role뿐 아니라 ClusterRole도 참조 가능하며, 이때 권한은 **그 네임스페이스 안으로만** 제한된다.
  - **ClusterRoleBinding** = 클러스터 전역 부여. **오직 ClusterRole만** 참조 가능(Role 불가 — 4조합 중 유일한 불가 조합).
  - **`roleRef`는 불변(immutable)**: 바꾸려면 바인딩 삭제 후 재생성.
  - **RBAC은 additive(더하기 전용)**: deny가 없다. 권한은 합집합으로 쌓이기만 하므로, 처음부터 최소권한만 주는 게 유일한 방어.
- **공식문서**:
  - <https://kubernetes.io/docs/reference/access-authn-authz/rbac/> — RoleBinding의 ClusterRole 참조(네임스페이스 한정 적용), roleRef 불변, allow 전용.
  - <https://kubernetes.io/docs/concepts/security/rbac-good-practices/> — 최소권한, 와일드카드·secrets get·전역 부여 지양.
- **면접 포인트**:
  - Q. ClusterRoleBinding으로 Role을 바인딩할 수 있나? → 불가. 전역 바인딩이 네임스페이스 스코프 역할을 가리키는 건 스코프 모순이라 API가 막는다. 단골 함정.
  - Q. 공용 역할을 여러 네임스페이스에서 재사용하려면? → ClusterRole 한 번 정의 + 네임스페이스마다 RoleBinding으로 참조. "ClusterRole = 무조건 전역"은 오해 — 전역 여부는 어떤 바인딩으로 붙이느냐가 결정.
  - Q. RBAC으로 특정 SA를 deny할 수 있나? → 없다. 애초에 권한을 안 주거나 NetworkPolicy·Admission 등 다른 계층으로 막는다. roleRef 수정도 edit 불가, 삭제·재생성이 정답.

## 🟡 왜 우리 서비스에서?
- 모니터링(`dang-obsv-ns`)의 Prometheus/kube-state-metrics는 전 네임스페이스 read가 본질적으로 필요 → 전용 SA에 read(get/list/watch) 전용 ClusterRole + **ClusterRoleBinding**(조합 2). secrets·쓰기는 처음부터 제외 — RBAC은 빼기가 안 되므로.
- 한 네임스페이스만 필요한 권한(`dang-vault-ns`, `dang-cert-manager-ns`의 configmap·secret read 등)은 Role + **RoleBinding**(조합 1). 공용 역할은 ClusterRole 한 번 정의 후 각 네임스페이스에서 RoleBinding으로 재사용(조합 3).
- 안티패턴 금지: Role+ClusterRoleBinding 시도(불가), default SA에 넓은 권한 몰아주기(익명 파드가 상속받는 사고 — "default SA 금지"와 짝).
- `roleRef` 불변이므로 권한 범위 변경은 GitOps 매니페스트에서 바인딩 삭제·재생성으로 관리.
- 검증은 수동 워크스루: `kubectl auth can-i --as=system:serviceaccount:dang-obsv-ns:prometheus-sa`로 사칭 확인 + `kubectl get clusterrolebinding,rolebinding -A` 점검, Kyverno로 과도한 CRB 금지 규칙 강제.
