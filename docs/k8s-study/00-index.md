# study in k8s — 오브젝트 명세서 (보안·모니터링 중요도순)

> 팀 공유용 학습 노트 28종. 각 문서는 **🟡 무엇인가**(정의·핵심·공식근거·면접 포인트) + **🟡 왜 우리 서비스에서?**(당당 적용) 2섹션 구조 — 노션 콜아웃 2개에 그대로 대응.
> 번호 = 보안·모니터링(김지훈 담당) 관련도 순.

## 🔴 Tier 1 · 보안 핵심 (01~14) — 직접 구축·설정하는 것

1. [PSA (Pod Security Admission)](<01-PSA (Pod Security Admission).md>)
2. [SecurityContext](<02-SecurityContext.md>)
3. [NetworkPolicy](<03-NetworkPolicy.md>)
4. [SA (ServiceAccount)](<04-SA (ServiceAccount).md>)
5. [Role](<05-Role.md>)
6. [ClusterRole](<06-ClusterRole.md>)
7. [RoleBinding & CRB (ClusterRoleBinding)](<07-RoleBinding & CRB (ClusterRoleBinding).md>)
8. [Secret](<08-Secret.md>)
9. [SealedSecret (Bitnami Sealed Secrets)](<09-SealedSecret (Bitnami Sealed Secrets).md>)
10. [etcd Encryption at Rest (저장 데이터 암호화)](<10-etcd Encryption at Rest (저장 데이터 암호화).md>)
11. [Certificate · Issuer (cert-manager)](<11-Certificate · Issuer (cert-manager).md>)
12. [Kyverno Policy · ClusterPolicy](<12-Kyverno Policy · ClusterPolicy.md>)
13. [Admission Webhook (Validating·MutatingWebhookConfiguration)](<13-Admission Webhook (Validating·MutatingWebhookConfiguration).md>)
14. [Audit Policy (감사 로깅)](<14-Audit Policy (감사 로깅).md>)

## 🔵 Tier 2 · 모니터링 핵심 (15~22) — 관측 스택 그 자체

15. [StatefulSet](<15-StatefulSet.md>)
16. [DaemonSet](<16-DaemonSet.md>)
17. [ServiceMonitor · PodMonitor (Prometheus Operator CRD)](<17-ServiceMonitor · PodMonitor (Prometheus Operator CRD).md>)
18. [PrometheusRule (Prometheus Operator CRD)](<18-PrometheusRule (Prometheus Operator CRD).md>)
19. [Probes (liveness · readiness · startup)](<19-Probes (liveness · readiness · startup).md>)
20. [HPA (HorizontalPodAutoscaler) + Metrics API](<20-HPA (HorizontalPodAutoscaler) + Metrics API.md>)
21. [PV (PersistentVolume) & PVC (PersistentVolumeClaim)](<21-PV (PersistentVolume) & PVC (PersistentVolumeClaim).md>)
22. [StorageClass](<22-StorageClass.md>)

## ⚪ Tier 3 · 공통 기반 (23~28) — 알아야 하지만 전담은 아님

23. [Namespace](<23-Namespace.md>)
24. [Service (ClusterIP · NodePort · LoadBalancer · Headless)](<24-Service (ClusterIP · NodePort · LoadBalancer · Headless).md>)
25. [Deployment](<25-Deployment.md>)
26. [ResourceQuota](<26-ResourceQuota.md>)
27. [LimitRange](<27-LimitRange.md>)
28. [PDB (PodDisruptionBudget)](<28-PDB (PodDisruptionBudget).md>)

---

### 정렬 기준
- **Tier 1 먼저**: 발표·질의에서 "보안을 어떻게 설계했나"가 먼저 검증되는 영역 + RBAC 4조합·PSA처럼 틀리기 쉬운 개념이 몰려 있음
- **Tier 2**: 이미 도커에서 운영해 본 익숙한 영역이라 학습 리스크가 낮아 뒤에
- **CRD 병기**: ServiceMonitor·PrometheusRule·SealedSecret·Certificate·Kyverno Policy는 K8s 내장이 아닌 커스텀 리소스(CRD) — 제목에 출처를 병기 (면접 단골 구분 질문)
