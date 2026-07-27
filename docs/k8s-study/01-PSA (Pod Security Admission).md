# PSA (Pod Security Admission)

## 🟡 무엇인가

- **한 줄 정의**: 파드 생성 시 보안 설정을 **네임스페이스 라벨** 기준으로 검사해 통과/거부/경고를 결정하는, 쿠버네티스 **기본 내장 어드미션 컨트롤러**다 (v1.25 GA, PSP의 후계).

- **핵심 개념**:
  - **3개 레벨(PSS)**: `privileged`(무제한) → `baseline`(알려진 권한 상승만 차단) → `restricted`(하드닝 모범사례 강제). 누적적이라 restricted는 baseline을 포함.
  - **3개 모드**: `enforce`(위반 파드 거부), `audit`(감사 로그만), `warn`(경고만). 독립적이라 한 네임스페이스에 서로 다른 레벨로 동시 적용 가능(예: enforce=baseline + warn=restricted).
  - **네임스페이스 라벨로 강제**: `pod-security.kubernetes.io/<mode>: <level>`. 파드 단위가 아니라 **네임스페이스 단위** 정밀도.
  - **워크로드 리소스 함정(가장 중요)**: `enforce`는 **최종 파드에만** 적용된다. 위반 Deployment는 apply가 성공하지만 파드가 거부되어 **레플리카 0으로 조용히 실패**한다. warn/audit은 워크로드 리소스에도 적용되므로 함께 건다.
  - **버전 고정**: `<mode>-version: v1.xx` 라벨로 규정 버전을 고정해, 클러스터 업그레이드 시 규정이 조용히 강화되는 사고를 방지.
  - **예외(exemption)**: AdmissionConfiguration으로 특정 사용자·RuntimeClass·네임스페이스 제외 가능.

- **공식문서**:
  - [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) — 3레벨 정의와 각 레벨의 요구 컨트롤(runAsNonRoot, capabilities drop ALL, seccomp 등).
  - [Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/) — 라벨 형식·3모드·"enforce는 파드에만 적용" 규칙 명시.

- **면접 포인트**:
  - **Q. PSA vs PSP?** → PSP는 v1.25에서 완전 제거. RBAC 바인딩 기반이라 적용 예측이 어려웠고, PSA는 네임스페이스 라벨 기반이라 단순·예측 가능.
  - **Q. baseline vs restricted?** → baseline은 명백히 위험한 것(privileged, hostNetwork, hostPath 등)만 차단. restricted는 추가로 runAsNonRoot·allowPrivilegeEscalation=false·capabilities.drop=[ALL]·seccomp 명시·볼륨 타입 제한까지 요구.
  - **Q. enforce=restricted면 잘못된 Deployment apply가 실패하나?** → 아니다. apply는 성공하고 파드만 거부돼 레플리카 0. 그래서 warn/audit을 같은 레벨로 함께 걸어 apply 시점에 경고를 보게 한다.

## 🟡 왜 우리 서비스에서?

- 당당(zerodang) K8s 이관의 **1차 방어선**: `dang-fe-ns`·`dang-be-ns`·`dang-ai-ns` 등에 `enforce: restricted` 적용 — 위험 설정을 코드 리뷰 없이 자동 차단.
- 우리 결정(2026-07-26 정정): **"PSA restricted 원칙 + 완화 최소"** — `dang-db-ns`만 `baseline`(root로 도는 DB 이미지는 restricted 전용 요구 runAsNonRoot 위반일 뿐이라 baseline으로 충분). node-exporter·OTel Agent의 hostPath·hostNetwork는 **공식 PSS상 baseline에서도 금지**("HostPath volumes must be forbidden" — Baseline 표)라, 해당 DaemonSet만 전용 네임스페이스로 분리해 `privileged`를 최소 범위 적용. 나머지 관측 스택(Prometheus 등)은 restricted 유지(PVC는 restricted 허용 볼륨). "필요한 만큼만 완화" 원칙.
- 워크로드 함정 대비: restricted 네임스페이스에 `warn`·`audit`도 restricted로 함께 걸고, `-version` 라벨로 버전 고정을 표준화.
- 다층 방어의 첫 관문: PSA(기준선) → SecurityContext(파드별 실제 값) → Kyverno(`dang-kyverno-ns`, 세밀한 맞춤 정책) 순으로 이어진다.
