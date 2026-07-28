# Admission Webhook (Validating·MutatingWebhookConfiguration)

## 🟡 무엇인가

- **한 줄 정의**: API 서버가 리소스를 etcd에 저장하기 직전, 외부 HTTP 서비스를 호출해 요청을 검증(Validating)하거나 수정(Mutating)하게 하는 확장 지점이며, `ValidatingWebhookConfiguration`/`MutatingWebhookConfiguration`으로 등록한다.

- **핵심 개념**:
  - **처리 순서**: 인증 → 인가 → **Mutating** → 스키마 검증 → **Validating** → etcd 저장. Mutating이 먼저라 수정된 최종 오브젝트를 Validating이 검사한다.
  - **두 종류**: Mutating은 오브젝트 수정(사이드카 주입, 기본값 채움), Validating은 허용/거부만 가능(변형 불가).
  - **왕복 구조**: API 서버가 `AdmissionReview` JSON을 TLS(HTTPS + `caBundle`)로 웹훅에 POST → 웹훅이 허용/거부 또는 JSONPatch를 응답.
  - **`failurePolicy`**: 웹훅 장애·타임아웃 시 `Fail`(요청 거부, 기본값) vs `Ignore`(통과). 정책 미집행 위험 vs 클러스터 마비 위험의 트레이드오프.
  - **매칭 규칙**: `rules`(operations/apiGroups/resources/scope)와 `namespaceSelector`/`objectSelector`로 대상 범위를 좁힌다. `timeoutSeconds` 기본 10초, 짧게 권장.
  - **`reinvocationPolicy: IfNeeded`**(Mutating 전용): 다른 플러그인이 오브젝트를 또 바꾸면 mutating 웹훅을 재호출.

- **공식문서**:
  - <https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/> — 동적 어드미션 컨트롤: Mutating→Validating 순서, timeoutSeconds, reinvocationPolicy.
  - <https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/> — 내장 어드미션 컨트롤러 목록과 요청 처리 파이프라인.

- **면접 포인트**:
  - **Q. Mutating과 Validating 중 무엇이 먼저?** → Mutating이 먼저. 수정된 최종 오브젝트를 Validating이 검사해야 하며, Validating은 오브젝트를 바꿀 수 없다.
  - **Q. Admission Controller와 Webhook의 관계?** → 컨트롤러는 API 서버 내장 플러그인이고, 그중 `MutatingAdmissionWebhook`/`ValidatingAdmissionWebhook` 두 플러그인이 외부 웹훅을 호출하는 확장 창구다.
  - **Q. `failurePolicy: Fail`의 위험?** → 웹훅 서비스가 죽으면 매칭되는 모든 요청이 막혀 배포가 마비될 수 있다. 그래서 kube-system 제외 + 범위 축소가 필수. (참고: `ValidatingAdmissionPolicy`는 CEL 기반 인-프로세스 검증으로 별개 기능 — 혼동 주의.)

## 🟡 왜 우리 서비스에서?

- 김지훈 담당 보안 3축 — **Kyverno·cert-manager·Vault Agent Injector** — 이 전부 이 웹훅 메커니즘 위에서 동작한다. 직접 웹훅을 짜진 않지만 트러블슈팅의 원리다.
- **Kyverno**(`dang-kyverno-ns`): ClusterPolicy에 맞춰 웹훅을 동적 등록 — restricted 못 켠 완화 ns(`dang-db-ns`=baseline, 관측 에이전트 전용 ns=privileged)에도 Harbor 이미지·`runAsNonRoot` 강제(validate), 라벨·기본 requests 주입(mutate).
- **Vault Agent Injector**(`dang-vault-ns`): 순수 Mutating 웹훅. `vault.hashicorp.com/agent-inject: true` 파드(`dang-be-ns`·`dang-ai-ns`)에 사이드카를 주입해 앱 코드 변경 없이 시크릿 전달. `failurePolicy: Ignore`가 무난(주입 실패 < 클러스터 마비).
- **운영 리스크**: 웹훅은 요청 경로의 직렬 단일 장애점 — kube-system·도구 자신 네임스페이스 제외, `namespaceSelector`로 `dang-*` 앱 네임스페이스만, `timeoutSeconds` 짧게.
- **관측 연결**: 배포가 이유 없이 실패하면 `apiserver_admission_webhook_*` 지표(rejection/latency)를 monitoring VM의 Prometheus/Loki 읽기전용 경로로 먼저 확인하는 것이 표준 절차.
