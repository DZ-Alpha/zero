# Audit Policy (감사 로깅)

## 🟡 무엇인가

- **한 줄 정의**: kube-apiserver를 거치는 모든 요청을 "누가·언제·무엇을·어디서·결과"로 규칙에 따라 기록하는 보안 감사 설정이다.

- **핵심 개념**:
  - **4가지 레벨**: `None` → `Metadata`(요청자·시각·리소스·verb) → `Request`(+요청 본문) → `RequestResponse`(+응답 본문). 아래로 갈수록 상세하고 로그량 증가.
  - **첫 매칭 승리**: rules를 위에서부터 평가해 처음 일치한 규칙의 level 적용 — 구체적 예외를 위에, catch-all을 맨 아래에.
  - **4가지 스테이지**: `RequestReceived` · `ResponseStarted`(watch 등 장시간) · `ResponseComplete` · `Panic`. `omitStages`로 중복·소음 제거.
  - **2가지 백엔드**: Log(JSON Lines 파일, `--audit-log-path`) / Webhook(원격 전송). 파일 기록 후 수집기로 나르는 방식이 일반적.
  - **핵심 플래그**: `--audit-policy-file`, `--audit-log-path`, `--audit-log-maxage`/`-maxbackup`/`-maxsize`(보관·회전).
  - **차등 기록이 설계 핵심**: 중요 리소스는 상세히, 반복 watch는 `None` — 전부 상세히 남기면 로그 폭증.

- **공식문서**:
  - [Auditing](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/) — 레벨·스테이지·백엔드·플래그와 첫 매칭 규칙 동작.
  - [kube-apiserver Audit Configuration (v1)](https://kubernetes.io/docs/reference/config-api/apiserver-audit.v1/) — `audit.k8s.io/v1` Policy/PolicyRule 스키마와 이벤트 필드 정의.

- **면접 포인트**:
  - **Q. 감사 로그 vs 앱 로그?** → 감사 로그는 API 서버를 지나는 제어면 활동, 앱 로그는 컨테이너 내부 동작. "누가 이 리소스를 바꿨나"는 감사 로그만 답한다.
  - **Q. 기본으로 켜져 있나?** → 아니다. `--audit-policy-file`과 백엔드 플래그를 명시해야 활성화 — 흔한 오해.
  - **Q. 왜 전부 RequestResponse로 안 남기나?** → 로그 폭증·성능 비용에 더해 응답 본문에 Secret 값이 섞여 감사 로그가 유출 표적이 된다. Secret은 보통 `Metadata`로만. 또 catch-all을 맨 위에 두면 아래 예외 규칙이 절대 도달 못 한다(순서가 곧 정책).

## 🟡 왜 우리 서비스에서?

- 다층 방어(PSA restricted, RBAC, NetworkPolicy default-deny, 시크릿 2계층, etcd 암호화)가 "실제로 지켜지는지, 누가 뚫으려 했는지"를 사후 증명하는 유일한 근거가 감사 로그다.
- `dang-vault-ns`·`dang-sealed-secrets-ns`의 Secret `get`/`list`를 `Metadata`로 기록 — 접근 시도는 포착하되 값 본문은 안 남겨 감사 로그 자체가 새 유출 경로가 되지 않음("추적 파일에 평문 금지" 규칙과 같은 정신).
- 마스터 3대의 감사 로그 파일을 `dang-obsv-ns`의 **OTel Collector Agent(DaemonSet)**가 tail → **Loki** → Grafana LogQL 조회, 이상 패턴(예: `dang-db-ns` 예상 밖 exec)은 Alertmanager 알림.
- 자원 제약(마스터 각 5GB/4CPU)상 차등 기록: 민감 리소스(Secret·RBAC·NetworkPolicy 변경)는 `Metadata` 이상, kube-system 반복 read/watch는 `None`, `RequestReceived`는 `omitStages`로 제외.
- **리스크**: `--audit-policy-file` 적용은 kube-apiserver 정적 Pod 수정·재기동을 수반하는 live 제어면 변경 — 리스크 제시 후 승인받고 적용. 로그 회전(`-maxsize`/`-maxbackup`)과 디스크 용량 관측 필수.
