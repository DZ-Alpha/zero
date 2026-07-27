# Kyverno Policy / ClusterPolicy

## 🟡 무엇인가

- **한 줄 정의**: 리소스가 지켜야 할 규칙을 YAML로 선언하면 Kyverno가 어드미션 단계에서 **검사(validate)·수정(mutate)·생성(generate)** 해 주는 정책 오브젝트다(`ClusterPolicy`=클러스터 범위, `Policy`=네임스페이스 범위).
- **핵심 개념**:
  - **rule 구조**: 각 rule은 `match`(+선택적 `exclude`) + validate/mutate/generate/verifyImages **중 정확히 하나**. 웹훅 코드를 직접 짜지 않고 YAML만 선언 → Policy as Code(Git/PR/GitOps)가 자연스럽다.
  - **적용 순서**: 어드미션 파이프라인이 mutating→validating 순이라 **mutate가 validate보다 먼저** 실행 — mutate 결과가 validate와 모순되면 안 된다.
  - **`failureAction`**: `Enforce`=요청 차단, `Audit`=허용하되 PolicyReport 기록(v1.13+ rule 단위 필드 — 구 `validationFailureAction`은 deprecated). Audit으로 관측 → 안정화 후 Enforce 승격이 정석.
  - **웹훅 자동 구성**: 정책 내용에 맞춰 Validating/MutatingWebhookConfiguration을 동적으로 좁게 등록 — 매칭 정책 없는 요청은 Kyverno로 오지 않는다.
  - **background scan**: 신규 차단뿐 아니라 기존 리소스도 스캔해 PolicyReport 생성(감사 겸용). generate는 `synchronize: true`로 파생 리소스 동기화.
- **공식문서**:
  - https://kyverno.io/docs/policy-types/cluster-policy/overview/ — 스코프와 rule 구성(match/exclude + 4종 중 하나).
  - https://kyverno.io/docs/policy-types/cluster-policy/validate/ — `failureAction`(Enforce=차단 / Audit=리포트만).
- **면접 포인트**:
  - **Q. Kyverno vs PSA?** → PSA는 내장 어드미션의 3단계 고정 프로파일이라 세밀 조정 불가. Kyverno는 임의 조건(레지스트리 제한, latest 금지 등)+mutate/generate까지. 배타가 아니라 PSA=넓은 벽 / Kyverno=세밀 보완으로 병용.
  - **Q. Kyverno vs OPA/Gatekeeper?** → Gatekeeper는 Rego 별도 언어, Kyverno는 쿠버네티스 YAML 그대로 — 학습 곡선 낮고 mutate·generate가 1급 기능.
  - **Q. Kyverno 파드가 죽으면 클러스터가 멈추나?** → 웹훅 `failurePolicy`에 달렸다. `Fail`이면 매칭 요청이 막힐 수 있어 Kyverno 자신·kube-system은 제외하거나 `Ignore`가 안전.

## 🟡 왜 우리 서비스에서?

- `dang-kyverno-ns`에 Kyverno를 두고 클러스터 규칙을 `ClusterPolicy`로 코드화 — 규칙 위반 매니페스트는 애초에 클러스터에 못 들어오고(shift-left), Git PR로 정책 이력이 남는다.
- **PSA 빈틈 보완이 최대 쓰임**: `dang-db-ns`는 `baseline`(root DB 이미지), 관측 에이전트 전용 ns는 `privileged`(hostPath·hostNetwork는 baseline도 금지 — 01 문서 정정) → 이 완화 구간을 validate로 세밀히 조인다(Harbor 레지스트리 강제, `latest` 금지, `runAsNonRoot`·`allowPrivilegeEscalation:false`·`capabilities.drop:[ALL]`·seccomp `RuntimeDefault` 필수).
- **mutate**: 식별 라벨 자동 주입, requests/limits 누락 시 도커 실측 기반 기본값 부여(워커 8Gi/2CPU 상한 결정과 연동).
- **generate**: 새 `dang-*` 네임스페이스 생성 즉시 default-deny NetworkPolicy 자동 생성 — fe→be→db 3계층 격리의 첫 벽을 사람 실수 없이 보장.
- 운영 원칙: Kyverno 자신·`kube-system` 등 부트스트랩 경로는 정책 제외, 신규 정책은 `Audit`으로 관측 후 `Enforce` 승격 — "리스크를 먼저 보고 결정" 원칙과 일치.
