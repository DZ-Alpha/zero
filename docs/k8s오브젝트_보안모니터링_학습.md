# K8s 오브젝트 학습 — 보안 & 모니터링 (김지훈 담당)

> 각 오브젝트: **무엇인가(정의)** + **왜 우리 서비스에서?(당당 적용)**
> 담당 네임스페이스: `dang-obsv-ns`(모니터링) · `dang-vault-ns`·`dang-cert-manager-ns`·`dang-kyverno-ns`·`dang-sealed-secrets-ns`(보안)

---

# Ⅰ. 네임스페이스 & 격리

## Namespace
> **무엇인가** — 클러스터를 논리적으로 나누는 격리 단위. 이름 스코프 + RBAC/NetworkPolicy/Quota/PSA를 거는 경계. (강한 격리는 별도 클러스터, namespace는 soft isolation)
> **왜 우리 서비스에서?** — 모니터링(`dang-obsv-ns`)·보안 도구별(`dang-vault-ns` 등)로 분리해 각 ns에 강한 정책을 건다. 특히 Vault는 시크릿 저장소라 폭발 반경 격리 목적으로 전용 ns.

## ResourceQuota
> **무엇인가** — 네임스페이스 전체가 쓸 수 있는 CPU/메모리/파드수/PVC 총량 상한.
> **왜 우리 서비스에서?** — `dang-obsv-ns`가 노드 자원을 독식하지 않게 상한을 건다(Prometheus 카디널리티 폭증 대비).

## LimitRange
> **무엇인가** — 네임스페이스 내 개별 컨테이너의 기본/최대/최소 requests·limits를 강제.
> **왜 우리 서비스에서?** — requests를 안 적은 워크로드에 기본값을 주고, 한 파드가 과도한 limit을 못 걸게 상한. `@Node`의 워커 8Gi/2CPU 기준으로 설정.

---

# Ⅱ. Pod 보안

## Pod Security Admission (PSA) / Pod Security Standards
> **무엇인가** — 네임스페이스 라벨(`pod-security.kubernetes.io/enforce`)로 파드 생성 시 보안 수준을 강제하는 내장 어드미션. 3레벨: privileged / baseline / **restricted**.
> **왜 우리 서비스에서?** — 일반 워크로드 ns는 restricted. 단 `dang-obsv-ns`는 node-exporter·otel-agent가 hostPath(/proc,/var/log) 필요라 **baseline**. (예외 사유 문서화)

## SecurityContext
> **무엇인가** — 파드/컨테이너의 실제 보안 설정: runAsNonRoot·allowPrivilegeEscalation:false·capabilities.drop:[ALL]·seccompProfile:RuntimeDefault·readOnlyRootFilesystem.
> **왜 우리 서비스에서?** — restricted를 만족시키는 구체 값. PSA(=상한)를 워크로드가 실제로 지키게 하는 설정. otel-gateway·grafana 등은 전부 restricted 수준으로.

---

# Ⅲ. 인증·인가 (RBAC)

## ServiceAccount (SA)
> **무엇인가** — 워크로드(파드)가 K8s API에 인증할 때 쓰는 신분. K8s엔 사람용 User 오브젝트가 없고, 워크로드는 SA로 인증.
> **왜 우리 서비스에서?** — Prometheus·kube-state-metrics·otel-collector는 전용 SA + ClusterRole(클러스터 read). API 안 쓰는 워크로드는 `automountServiceAccountToken:false`.

## Role
> **무엇인가** — **특정 네임스페이스 안**에서 어떤 리소스에 어떤 동작(get/list/watch 등)을 허용하는 권한 묶음.
> **왜 우리 서비스에서?** — ns 범위 권한이 필요한 경우(예: 특정 ns의 configmap read).

## ClusterRole
> **무엇인가** — **클러스터 전역** 권한 묶음. 노드·PV 같은 non-namespaced 리소스나 여러 ns를 아우르는 권한.
> **왜 우리 서비스에서?** — Prometheus(서비스 디스커버리로 전 ns의 pods/services/endpoints read), kube-state-metrics(전 오브젝트 read)는 ClusterRole 필수.

## RoleBinding / ClusterRoleBinding
> **무엇인가** — Role/ClusterRole을 SA(또는 그룹)에 **연결**. 4조합: Role+RoleBinding(ns), ClusterRole+ClusterRoleBinding(전역), **ClusterRole+RoleBinding(공용역할을 특정 ns에만)**, Role+ClusterRoleBinding(불가).
> **왜 우리 서비스에서?** — prometheus-sa ↔ ClusterRole 을 ClusterRoleBinding으로 연결. RBAC은 거부 없이 더하기만 → **최소권한만** 부여. 검증 `kubectl auth can-i`.

---

# Ⅳ. 네트워크 보안

## NetworkPolicy
> **무엇인가** — 파드 간/네임스페이스 간 L3/L4 트래픽 허용 규칙. 기본은 전부 허용 → 정책이 파드를 선택하면 격리. `podSelector:{}`+policyTypes = default-deny. **지원 CNI(Calico/Cilium) 필수**.
> **왜 우리 서비스에서?** — 각 ns에 default-deny 후 필요한 것만 허용(fe→be→db 3계층). `dang-obsv-ns`는 Prometheus가 전 ns로 나가는 scrape egress + Grafana 접근 ingress만.

---

# Ⅴ. 시크릿 & 인증서

## Secret
> **무엇인가** — 민감 데이터(비밀번호·토큰·키)를 담는 오브젝트. 타입: Opaque, kubernetes.io/dockerconfigjson(imagePull), kubernetes.io/tls. **기본은 base64일 뿐 암호화 아님** → etcd 암호화 병행 필요.
> **왜 우리 서비스에서?** — DB 자격증명·Slack webhook·Grafana admin 등. 평문 저장 금지, Sealed Secrets/Vault로 관리 + etcd 암호화.

## SealedSecret (cert-manager 아님 — Bitnami CRD)
> **무엇인가** — 공개키로 암호화해 **Git에 안전하게 커밋**할 수 있는 Secret. 클러스터의 controller만 개인키로 복호화 → 일반 Secret 생성.
> **왜 우리 서비스에서?** — GitOps(ArgoCD) 부트스트랩 시크릿(imagePullSecret 등)을 Git에 올리려고. `dang-sealed-secrets-ns`의 controller. **sealing key 백업 필수(유실=복호화 불가)**.

## Certificate / Issuer / ClusterIssuer (cert-manager CRD)
> **무엇인가** — cert-manager가 TLS 인증서를 **자동 발급·갱신**하게 하는 CRD. Issuer(ns 범위)/ClusterIssuer(전역)가 발급 주체, Certificate가 발급 요청.
> **왜 우리 서비스에서?** — Ingress/게이트웨이 TLS를 수동 갱신 없이 자동으로. 핵심은 "발급"보다 **자동 갱신 + 만료 알람**.

---

# Ⅵ. 정책 엔진 (Admission)

## Policy / ClusterPolicy (Kyverno CRD)
> **무엇인가** — Kyverno가 파드 생성/변경을 검증(validate)·변형(mutate)·생성(generate)하는 정책 규칙. ClusterPolicy(전역)/Policy(ns).
> **왜 우리 서비스에서?** — "모든 파드는 runAsNonRoot여야 한다", "latest 태그 금지", "네임스페이스에 라벨 강제" 같은 조직 규칙을 코드로 강제. PSA가 못 하는 세밀한 규칙 보완.

## ValidatingWebhookConfiguration / MutatingWebhookConfiguration
> **무엇인가** — API 서버가 오브젝트를 저장하기 전에 외부 webhook(검증/변형)을 호출하게 하는 설정. Kyverno·cert-manager·Vault injector가 이걸로 동작.
> **왜 우리 서비스에서?** — 직접 만들진 않지만, Kyverno(검증)·Vault injector(시크릿 주입)·cert-manager(webhook)가 내부적으로 등록. **이게 있어야 정책·주입이 작동함을 이해**.

---

# Ⅶ. 모니터링 — 수집

## Service
> **무엇인가** — 파드 집합에 안정적인 가상 IP/DNS를 부여하는 오브젝트(ClusterIP/NodePort/LoadBalancer/Headless).
> **왜 우리 서비스에서?** — Prometheus가 scrape할 대상 엔드포인트를 Service로 노출. StatefulSet(Prometheus 등)은 Headless Service로 안정 신원 제공.

## ServiceMonitor / PodMonitor (Prometheus Operator CRD)
> **무엇인가** — "이 라벨의 Service/Pod를 이 경로·주기로 scrape하라"를 선언하는 CRD. Prometheus 설정을 직접 안 건드리고 CRD로 관리.
> **왜 우리 서비스에서?** — 각 워크로드의 `/metrics`를 ServiceMonitor로 등록 → Prometheus가 자동 발견·수집. 설정을 코드(GitOps)로.

## PrometheusRule (Prometheus Operator CRD)
> **무엇인가** — 알림 규칙(alerting rule)과 기록 규칙(recording rule)을 담는 CRD.
> **왜 우리 서비스에서?** — "인스턴스 Down", "메모리 90% 초과" 같은 알람을 코드로 정의 → Alertmanager로 발화. (현재 Grafana Alerting은 provenance=api로 관리 중)

---

# Ⅷ. 워크로드 컨트롤러 (관측 관점)

## Deployment
> **무엇인가** — 무상태(stateless) 워크로드를 원하는 replica 수로 유지·롤링업데이트하는 컨트롤러.
> **왜 우리 서비스에서?** — Grafana·otel-gateway·kube-state-metrics·cert-manager·kyverno 등 상태 없는 것들. (스토리지 없음 → claimName 빈칸)

## StatefulSet
> **무엇인가** — 안정적 신원(pod-0..N) + 파드별 영속 볼륨(volumeClaimTemplates)이 필요한 워크로드. 순서 있는 배포/스케일.
> **왜 우리 서비스에서?** — Prometheus·Loki·Tempo·Alertmanager·Vault. 각자 자기 디스크(TSDB/WAL/Raft)를 쓰고 HA에 고정 신원이 필요.

## DaemonSet
> **무엇인가** — 모든(또는 선택된) 노드마다 파드 1개를 띄우는 컨트롤러.
> **왜 우리 서비스에서?** — node-exporter(노드 메트릭)·otel-agent(노드별 로그 수집). 노드마다 있어야 하는 게 정의 그 자체.

---

# Ⅸ. 스토리지 (관측 데이터 영속)

## PersistentVolume (PV) / PersistentVolumeClaim (PVC)
> **무엇인가** — PV=실제 스토리지 자원, PVC=워크로드의 스토리지 요청. 파드는 PVC를 마운트하고, PVC는 PV에 바인딩됨.
> **왜 우리 서비스에서?** — Prometheus TSDB, Loki/Tempo WAL, Alertmanager silence, Vault Raft. StatefulSet은 volumeClaimTemplates로 PVC 자동생성.

## StorageClass
> **무엇인가** — PVC 요청 시 PV를 어떤 프로비저너로 동적 생성할지 정의(Longhorn 등).
> **왜 우리 서비스에서?** — Longhorn CSI가 각 모니터링 PVC를 동적 공급. 청크 장기저장은 MinIO(오브젝트).

---

# Ⅹ. 오토스케일 · 헬스 · 가용성

## HorizontalPodAutoscaler (HPA) + Metrics API
> **무엇인가** — CPU/메모리 사용률에 따라 replica 수를 자동 조절. metrics-server가 Metrics API로 사용량을 공급.
> **왜 우리 서비스에서?** — metrics-server는 `dang-obsv-ns`가 아니라 kube-system. HPA는 주로 앱(재헌팀)이지만, **모니터링이 그 지표 파이프라인(cAdvisor→metrics-server→HPA)을 이해·검증**해야 함. HPA는 CPU 기준(메모리 기반은 scale-down 안 됨).

## PodDisruptionBudget (PDB)
> **무엇인가** — 자발적 중단(노드 드레인 등) 시 최소 가용 파드 수를 보장.
> **왜 우리 서비스에서?** — Alertmanager(×3) 같은 HA 워크로드가 노드 유지보수 중에도 정족수를 유지하게.

## Probes (liveness / readiness / startup)
> **무엇인가** — 컨테이너 헬스체크. liveness=죽으면 재시작, readiness=준비되면 트래픽, startup=느린 시작 보호.
> **왜 우리 서비스에서?** — 모든 모니터링/보안 워크로드에 설정. readiness가 안 되면 Service에서 빠져 관측 공백 방지. blackbox-exporter로 외부 관측점도 감시.

---

# ⚠️ 오브젝트는 아니지만 알아야 할 것 (컨트롤플레인 설정)

## etcd Encryption at Rest (EncryptionConfiguration)
> **무엇인가** — etcd에 저장되는 Secret 등을 암호화. Secret은 기본 base64라 이게 없으면 etcd 백업이 곧 시크릿 유출.
> **왜 우리 서비스에서?** — Sealed Secrets/Vault가 Git·런타임을 막아도, **K8s가 자체 생성하는 SA 토큰 등은 etcd에 남음** → 최후 방어선.

## Audit Policy (감사 로깅)
> **무엇인가** — API 서버에 대한 모든 요청을 기록하는 정책. 누가 언제 무엇을 했는지 추적.
> **왜 우리 서비스에서?** — 보안 사고 시 추적성. 감사 로그도 Loki로 수집하면 관측과 연결.

---

## 학습 우선순위 (12시간 안이면)
1. **PSA·SecurityContext** (내 시방서 PodSecurity 탭)
2. **RBAC 4조합·SA** (Role 탭)
3. **NetworkPolicy·CNI** (NetworkPolicy 탭)
4. **Secret·SealedSecret·Certificate** (Secret 탭)
5. 나머지는 각 시방서 탭 작성하며 자연 습득
