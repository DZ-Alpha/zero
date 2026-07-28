# SecurityContext

## 🟡 무엇인가

- **한 줄 정의**: 파드/컨테이너가 **어떤 사용자(UID)·권한·커널 능력으로 실행될지**를 지정해 최소 권한으로 가두는 매니페스트 필드다 — PSA가 검사(gate)한다면 SecurityContext는 그 검사를 통과할 값을 채운다.

- **핵심 개념**:
  - **`runAsNonRoot: true`**: UID 0(root)이면 실행 거부하는 검증 규칙. 실제 UID 지정은 `runAsUser`(예: 1000)로 — 둘은 함께 쓴다.
  - **`allowPrivilegeEscalation: false`**: 리눅스 `no_new_privs`를 켜 setuid 등으로 부모보다 높은 권한 획득을 차단. `privileged: true`는 이를 무력화하므로 절대 금지가 전제.
  - **`capabilities.drop: [ALL]`**: 커널 능력을 전부 버리고 필요한 것만 `add`로 복원(예: 1024 미만 포트용 `NET_BIND_SERVICE`). 최소 권한의 정석.
  - **`seccompProfile.type: RuntimeDefault`**: 런타임 기본 seccomp로 위험 시스템콜을 커널 수준 차단. restricted는 RuntimeDefault/Localhost **명시** 요구.
  - **`readOnlyRootFilesystem`(컨테이너 전용)**: 루트 FS 읽기 전용 — 강력한 모범사례지만 **restricted 필수 조건은 아님**.
  - **적용 위치**: 파드 레벨(`spec.securityContext`, runAsUser·fsGroup·seccomp 등 공통) vs 컨테이너 레벨(privileged·capabilities·readOnlyRootFilesystem 등 전용). 겹치면 **컨테이너 레벨이 덮어쓴다**.

- **공식문서**:
  - [Configure a Security Context for a Pod or Container](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/) — 파드/컨테이너 레벨 필드와 설정 방법.
  - [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) — restricted 요구 값 목록. readOnlyRootFilesystem은 이 목록에 없음.

- **면접 포인트**:
  - **Q. `runAsNonRoot` vs `runAsUser`?** → 전자는 "root면 거부"라는 검증, 후자는 실제 UID 지정. 전자만 켜고 이미지가 root면 시작 실패(CreateContainerError). 보완 관계.
  - **Q. `readOnlyRootFilesystem`은 restricted 필수?** → 아니다. 권장 모범사례일 뿐. 무작정 강제하면 임시파일 쓰는 앱이 깨져 emptyDir로 쓰기 경로만 열어 개별 적용한다.
  - **흔한 오해**: "파드 레벨이 항상 적용된다" — 겹치는 필드는 컨테이너 레벨이 우선. 또 `privileged: true`는 `allowPrivilegeEscalation: false`를 무력화한다.

## 🟡 왜 우리 서비스에서?

- 팀 표준 하드닝 4종 세트: `runAsNonRoot: true` + `allowPrivilegeEscalation: false` + `capabilities.drop: [ALL]` + `seccompProfile: RuntimeDefault` — `dang-fe-ns`·`dang-be-ns`·`dang-ai-ns`의 **PSA restricted를 통과하는 최소 조합**이라, 빠뜨리면 배포가 실패하도록 설계.
- 레벨 배치 원칙: 공통 값(runAsNonRoot·runAsUser·seccompProfile·fsGroup)은 파드 레벨, 컨테이너 전용 값은 컨테이너 레벨. 포트 바인딩 필요한 프런트/게이트웨이만 `add: [NET_BIND_SERVICE]` 최소 복원.
- `readOnlyRootFilesystem`은 전역 필수에서 제외 — restricted 조건이 아니고 백엔드/AI 워크로드가 깨지므로, 가능한 워크로드부터 emptyDir 병행으로 점진 적용. "필수와 권장을 정확히 구분" 원칙의 대표 사례.
- PSA를 완화한 곳(baseline인 `dang-db-ns`, privileged인 관측 에이전트 전용 ns — hostPath·hostNetwork는 baseline도 금지, 01 문서 정정 참조)에서도 하드닝 유지: 불가피한 최소 권한만 열고, 나머지는 SecurityContext로 자발적으로 조여 다층 방어 완성.
