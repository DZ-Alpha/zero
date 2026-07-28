# SA (ServiceAccount)

## 🟡 무엇인가
- **한 줄 정의**: 파드(워크로드)가 쿠버네티스 API 서버에 자기 신원을 증명할 때 쓰는 "기계용 신분증".
- **핵심 개념**:
  - **워크로드 아이덴티티**: 사람이 아니라 파드에 부여되는 신분. 파드는 `spec.serviceAccountName`으로 지정.
  - **User 오브젝트는 없다**: 쿠버네티스에는 일반 사용자 계정 오브젝트가 없고 API로 추가도 불가. 사람 인증은 인증서·OIDC 등 외부 수단 담당.
  - **default SA 자동 할당**: 모든 네임스페이스에 `default` SA가 있고, 파드가 지정하지 않으면 자동으로 붙어 토큰까지 마운트된다(`/var/run/secrets/kubernetes.io/serviceaccount`).
  - **자동마운트 차단**: `automountServiceAccountToken: false`로 토큰 볼륨 주입을 끈다. API를 안 쓰는 워크로드는 반드시 꺼서 토큰 탈취 피해를 줄인다. SA·파드 양쪽 설정 시 파드 spec 우선.
  - **바운드 토큰**: 현재 토큰은 TokenRequest API로 발급되는 시간·대상(audience)·파드에 묶인 단명 토큰(과거의 만료 없는 Secret 토큰과 다름).
  - **인증 ≠ 인가**: SA는 "누구인가"만 증명. "무엇을 할 수 있는가"는 RoleBinding/ClusterRoleBinding으로 별도 부여하며, 안 하면 권한 0.
- **공식문서**:
  - <https://kubernetes.io/docs/concepts/security/service-accounts/> — SA는 비인간(non-human) 대상 아이덴티티, default SA 자동 할당.
  - <https://kubernetes.io/docs/reference/access-authn-authz/authentication/> — 일반 사용자 오브젝트 없음·API 추가 불가, 사람은 외부 인증·워크로드는 SA.
- **면접 포인트**:
  - **Q. 쿠버네티스에서 User를 어떻게 만드나?** → 함정. 만들 수 없다. User 오브젝트가 없고, 사람은 인증서/OIDC 등 외부에서 인증된다.
  - **Q. default SA를 그대로 쓰면 뭐가 문제인가?** → 토큰이 자동 마운트돼 파드 침해 시 API 접근 발판이 된다. 워크로드별 전용 SA + 최소권한 + 불필요 시 automount 차단이 원칙.
  - **Q. SA를 만들면 권한이 생기나?** → 아니다. SA는 인증(신분)일 뿐, RoleBinding 연결 전 권한은 0. 반대로 권한이 없어도 토큰 마운트(신분 노출) 자체가 리스크다.

## 🟡 왜 우리 서비스에서?
- 이관 원칙: 워크로드마다 전용 SA. Prometheus는 `prometheus-sa` + 클러스터 전역 read ClusterRole/ClusterRoleBinding, kube-state-metrics도 동일 패턴. API를 거의 안 쓰는 OTel Collector 게이트웨이는 권한 최소 유지.
- 앱·DB 계층(dang-fe-ns, dang-be-ns, dang-ai-ns, dang-db-ns)은 API 호출이 불필요하므로 `automountServiceAccountToken: false`로 토큰을 아예 안 넣는다 — SecurityContext·NetworkPolicy default-deny와 같은 "최소 노출" 원칙.
- **default SA에 권한 부여 금지**: default에 바인딩하면 SA 미지정 파드 전부가 권한을 얻는 사고. 권한은 이름 있는 전용 SA에만 바인딩(RBAC 최소권한·폭발 반경 축소).
- 검증: `kubectl get pod -o yaml`로 토큰 볼륨 제거 확인, `kubectl auth can-i --as=system:serviceaccount:<ns>:<sa>`로 실제 권한 확인(수동 워크스루 원칙).
