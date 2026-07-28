# Certificate / Issuer (cert-manager)

## 🟡 무엇인가

- **한 줄 정의**: cert-manager가 TLS 인증서를 자동 발급·자동 갱신하도록 선언하는 CRD — `Issuer`/`ClusterIssuer`가 발급 기관, `Certificate`가 요청서다.
- **핵심 개념**:
  - **Issuer vs ClusterIssuer**: `Issuer`는 네임스페이스 범위(같은 ns의 Certificate만 참조 가능), `ClusterIssuer`는 클러스터 전역. 여러 ns가 한 발급 정책을 공유하면 ClusterIssuer.
  - **Issuer 종류**: `ACME`(Let's Encrypt 등 공인), `CA`/`SelfSigned`(사내 PKI·mTLS), Vault 등. 공인이면 ACME, 내부용이면 CA/SelfSigned.
  - **발급 파이프라인**: `Certificate` → 개인키 + `CertificateRequest` 생성 → Issuer 서명 → `kubernetes.io/tls` Secret(`tls.crt`/`tls.key`, 경우에 따라 `ca.crt`) 저장. ACME는 중간에 `Order`·`Challenge`(HTTP-01/DNS-01) 추가.
  - **자동 갱신**: 기본 duration 90일, 갱신은 기본 동작으로 수명의 2/3 지점(=만료 30일 전)에 시작 — `renewBefore`는 기본 미설정이며 명시하면 그 값이 우선. 진짜 가치는 최초 발급이 아니라 평생 자동 갱신이다.
  - **관측**: 9402 포트로 Prometheus 메트릭 노출 — `certmanager_certificate_expiration_timestamp_seconds`(만료 시각), `certmanager_certificate_ready_status`(0=실패/미준비).
- **공식문서**:
  - https://cert-manager.io/docs/concepts/issuer/ — Issuer(단일 ns) vs ClusterIssuer(전역) 스코프 정의.
  - https://cert-manager.io/docs/usage/certificate/ — Certificate 요청 정의와 Secret 저장 동작.
- **면접 포인트**:
  - **Q. Issuer vs ClusterIssuer 언제?** → Certificate는 같은 ns의 Issuer만 참조 가능. 여러 ns가 공통 정책(예: 공통 ACME 계정)을 쓰면 ClusterIssuer. 다른 ns Issuer 참조 시도는 흔한 발급 실패 원인.
  - **Q. 두 개의 `ca.crt` 구분은?** → 파드에 자동 마운트되는 클러스터 PKI ca.crt(kube-apiserver 검증용, cert-manager 무관) vs TLS Secret의 ca.crt(cert-manager CA/SelfSigned가 리프를 서명한 CA). 섞으면 TLS 디버깅에서 시간 낭비.
  - **Q. 갱신되면 오브젝트가 새로 생기나?** → 아니다. Certificate·Secret은 그대로, Secret 안 내용물(tls.crt/tls.key)만 교체. Ingress는 Secret 이름만 참조하므로 대개 무중단.

## 🟡 왜 우리 서비스에서?

- `dang-cert-manager-ns`에 cert-manager(controller·webhook·cainjector) 설치. 핵심 동기는 발급이 아닌 **자동 갱신 + 만료 알람** — 도커 시절 수동 인증서는 만료 장애 예약 구조였다.
- `dang-fe-ns`·`dang-obsv-ns` 등 여러 ns가 공유하므로 **ClusterIssuer 하나로 통일**: 외부 도메인은 ACME(Let's Encrypt), 내부 mTLS는 SelfSigned/CA 사설 PKI.
- 9402 메트릭을 `dang-obsv-ns` Prometheus가 ServiceMonitor로 수집 → `(expiration - time()) / 86400`으로 30일/7일 전 경보, `ready_status == 0`은 즉시 알람 → 기존 Alertmanager HA×3·Grafana Alerting으로 전달. "자동 갱신 실패"를 관측으로 잡는 게 설계 원칙.
- 두 `ca.crt` 구분 주의: Prometheus의 apiserver 검증은 클러스터 PKI(`kube-root-ca.crt`), Grafana Ingress 인증서는 cert-manager 발급분.
- cert-manager는 ValidatingWebhook으로 동작 → **webhook 파드 생존이 전제조건**, 이 의존성도 관측 대상.
