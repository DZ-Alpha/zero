# NetworkPolicy

## 🟡 무엇인가
- **한 줄 정의**: 어떤 파드가 어떤 대상과 통신할 수 있는지를 IP·포트 수준(L3/L4)에서 선언적으로 제어하는 쿠버네티스 방화벽 규칙.
- **핵심 개념**:
  - **기본은 전부 허용**: 파드는 기본적으로 비격리 상태. 어떤 정책이 파드를 선택하는 순간 격리되고, 그때부터 명시적으로 허용된 트래픽만 통과한다(화이트리스트 모델).
  - **`podSelector: {}`**: 네임스페이스의 모든 파드 선택. `policyTypes: [Ingress, Egress]`에 허용 규칙 없이 쓰면 default-deny(전부 차단)가 된다.
  - **`policyTypes` 함정**: 생략 시 Ingress는 항상 설정되지만 Egress는 egress 규칙이 있을 때만 설정된다. egress를 막으려면 `Egress`를 명시해야 한다.
  - **정책은 가산적**: 여러 정책이 한 파드를 선택하면 합집합 적용. 우선순위·명시적 deny는 없다.
  - **양방향 허용 필요**: 연결이 성립하려면 소스의 egress와 목적지의 ingress가 둘 다 허용해야 한다.
  - **CNI 필수·L3/L4 전용**: Calico·Cilium 등 정책 지원 CNI가 없으면(flannel 단독 등) 규칙은 오류 없이 조용히 무시된다. L7(HTTP 경로 등)은 제어 불가.
- **공식문서**:
  - [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/) — 비격리→격리 모델, L3/L4 범위, `policyTypes` 동작, CNI 필요성.
  - [NetworkPolicy API 레퍼런스](https://kubernetes.io/docs/reference/kubernetes-api/policy-resources/network-policy-v1/) — `podSelector`, `policyTypes`, from/to(podSelector·namespaceSelector·ipBlock), `ports` 스펙.
- **면접 포인트**:
  - **Q. 정책이 없는 네임스페이스는 안전한가?** → 아니다. 정책이 없으면 전부 허용. 보안을 원하면 먼저 default-deny를 깔아야 한다.
  - **Q. Ingress default-deny만 걸면 egress도 막히나?** → 아니다. `policyTypes`에 `Egress`를 넣지 않으면 나가는 트래픽은 그대로 열려 있다.
  - **Q. 정책을 잘 짰는데 왜 안 막히지?** → 십중팔구 CNI 미지원(flannel 단독 등). 리소스는 저장되지만 조용히 무시되므로 CNI부터 확인.

## 🟡 왜 우리 서비스에서?
- 당당 K8s 이관의 보안 축: 각 앱 네임스페이스(dang-fe-ns / dang-be-ns / dang-db-ns)에 `podSelector: {}` + `policyTypes: [Ingress, Egress]` default-deny를 깔고, fe→be→db 흐름만 화이트리스트로 개방. 파드가 탈취돼도 침해 반경이 한 계층에 갇힌다.
- **egress 통제가 핵심**: ingress만 막으면 탈취된 파드의 외부 데이터 유출·C2 통신을 못 막는다.
- **필수 예외 2개**: DNS(kube-system CoreDNS, UDP/TCP 53) egress 허용 — default-deny egress 도입 시 가장 흔한 장애 원인. 그리고 dang-obsv-ns의 Prometheus 스크레이프를 위해 `namespaceSelector`로 메트릭 포트만 ingress 개방.
- **전제: CNI는 Calico/Cilium**. 미지원 CNI면 전 정책이 조용히 무효가 되므로, 이관 체크리스트에 "default-deny 적용 후 파드 간 연결 테스트로 실제 차단 확인"을 포함(수동 워크스루 검증 원칙).
- PSA를 완화한 네임스페이스(baseline인 dang-db-ns, privileged인 관측 에이전트 전용 ns)도 NetworkPolicy 격리는 동일 적용 — PSA 예외와 네트워크 격리는 무관.
