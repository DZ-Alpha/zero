# AlphaCar — Kubernetes 인프라 시방서

> 원본: `k8s_DangDang_시방서.xlsx` (21개 시트). 병합 셀과 다중 행 레코드를 사람이 읽는 순서로 정리한 문서입니다.

> 이 문서는 **설계 의도(source of intent)** 이고, 실제 배포 매니페스트는 `manifests/` 에 있습니다. 발견된 이슈는 `REVIEW.md` 를 참고하세요.


> ⚠️ **보안 주의**: 원본에 DB 비밀번호와 AWS 자격증명이 평문으로 포함되어 있었습니다. AWS Secret Access Key 는 이 문서에서 마스킹했습니다. 반드시 `REVIEW.md` 의 보안 항목을 먼저 확인하세요.


## 목차

- [노드 (Cluster Nodes)](#노드-cluster-nodes)
- [네임스페이스 & 파드 배치](#네임스페이스-파드-배치)
- [ResourceQuota (네임스페이스별 자원 쿼터)](#resourcequota-네임스페이스별-자원-쿼터)
- [LimitRange (컨테이너 기본/최소/최대 자원)](#limitrange-컨테이너-기본-최소-최대-자원)
- [HPA (수평 파드 오토스케일러)](#hpa-수평-파드-오토스케일러)
- [Liveness / Readiness Probe](#liveness-readiness-probe)
- [Deployments (워크로드)](#deployments-워크로드)
- [StatefulSet](#statefulset)
- [PodSecurity (Pod Security Standards)](#podsecurity-pod-security-standards)
- [Service](#service)
- [ConfigMap](#configmap)
- [Secret](#secret)
- [RBAC (ServiceAccount / Role / Binding)](#rbac-serviceaccount-role-binding)
- [NetworkPolicy](#networkpolicy)
- [PersistentVolumeClaim](#persistentvolumeclaim)
- [PersistentVolume](#persistentvolume)
- [Job](#job)
- [CronJob](#cronjob)
- [AI Chat 백엔드 상세](#ai-chat-백엔드-상세)
- [AI 리뷰 분석 스크립트](#ai-리뷰-분석-스크립트)
- [AI 인프라 모니터링 대시보드](#ai-인프라-모니터링-대시보드)


## 노드 (Cluster Nodes)

_원본 시트: `Node` — 10행_

| node | memory | cpu | IP |
| --- | --- | --- | --- |
| DangDang-master1 | 5120MB | 3 | 192.168.0.170 |
| DangDang-master2 | 5120MB | 3 | 192.168.0.171 |
| DangDang-master3 | 5120MB | 3 | 192.168.0.172 |
| DangDang-worker1 | 3072MB | 2 | 192.168.0.173 |
| DangDang-worker2 | 3072MB | 2 | 192.168.0.174 |
| DangDang-worker3 | 3072MB | 2 | 192.168.0.175 |
| DangDang-worker4 | 3072MB | 2 | 192.168.0.176 |
| DangDang-worker5 | 3072MB | 2 | 192.168.0.177 |
| DangDang-proxy | 2048MB | 2 | 192.168.0.178 |


## 네임스페이스 & 파드 배치

_원본 시트: `NameSpace` — 31행_

| ns | pod | col3 |
| --- | --- | --- |
| alphacar-fe-ns | alphacar-fe |  |
| alphacar-be-ns | alphacar-main-be | 3002 |
| alphacar-be-ns | alphacar-quote-be | 3003 |
| alphacar-be-ns | alphacar-news-be | 3004 |
| alphacar-be-ns | alphacar-community-be | 3005 |
| alphacar-be-ns | alphacar-mypage-be | 3006 |
| alphacar-be-ns | alphacar-search-be | 3007 |
| alphacar-be-ns | alphacar-aichat-be | 4000 |
| alphacar-db-ns | alphacar-redis |  |
| alphacar-db-ns | alphacar-mongo |  |
| alphacar-db-ns | alphacar-maria |  |
| alphacar-obsv-ns | loki |  |
| alphacar-obsv-ns | prometheus |  |
| alphacar-obsv-ns | grafana |  |
| alphacar-obsv-ns | grafana alloy |  |
| alphacar-obsv-ns | tempo |  |
| alphacar-cicd-ns | jenkins |  |
| alphacar-cicd-ns | sonarqube |  |
| alphacar-cicd-ns | trivy |  |
| alphacar-cicd-ns | harbor |  |
| alphacar-cicd-ns | argocd |  |
| alphacar-istio-system | istio |  |
| alphaca-security-system | cert-manager |  |
| alphaca-security-system | kube-bench |  |
| alphaca-security-system | kyverno |  |
| alphacar-striming-ns | strimzi |  |
| alphacar-striming-ns | kafka |  |
| alphacar-backup-ns | longhorn |  |
| alphacar-backup-ns | velero |  |
| alphacar-chaos-ns | chaos mesh |  |


## ResourceQuota (네임스페이스별 자원 쿼터)

_원본 시트: `ResourceQuota` — 21행_

| NS | pods | requests | requests | limits | limits | persistentvolumeclaims | storage | qos |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| alphacar-fe-ns | 10 | cpu | 500m | cpu | 4CPU | - | - | Burstable |
| alphacar-fe-ns | 10 | memory | 1Gi | memory | 4Gi | - | - | Burstable |
| alphacar-be-ns | 30 | cpu | 4CPU | cpu | 12CPU | 5 | 50Gi | Burstable |
| alphacar-be-ns | 30 | memory | 6Gi | memory | 16Gi | 5 | 50Gi | Burstable |
| alphacar-db-ns | 10 | cpu | 2CPU | cpu | 6CPU | 5 | 100Gi | Burstable |
| alphacar-db-ns | 10 | memory | 3Gi | memory | 6Gi | 5 | 100Gi | Burstable |
| alphacar-obsv-ns | 15 | cpu | 2CPU | cpu | 8CPU | 5 | 100Gi | Burstable |
| alphacar-obsv-ns | 15 | memory | 3Gi | memory | 12Gi | 5 | 100Gi | Burstable |
| alphacar-cicd-ns | 30 | cpu | 8CPU | cpu | 16CPU | 15 | 200Gi | Burstable |
| alphacar-cicd-ns | 30 | memory | 8Gi | memory | 16Gi | 15 | 200Gi | Burstable |
| alphacar-istio-system | 15 | cpu | 2CPU | cpu | 4CPU | - | - | Burstable |
| alphacar-istio-system | 15 | memory | 1.5Gi | memory | 4Gi | - | - | Burstable |
| alphaca-security-system | 10 | cpu | 1CPU | cpu | 2CPU | - | - | BestEffort |
| alphaca-security-system | 10 | memory | 512Mi | memory | 2Gi | - | - | BestEffort |
| alphacar-striming-ns | 10 | cpu | 2CPU | cpu | 6CPU | 5 | 50Gi | Burstable |
| alphacar-striming-ns | 10 | memory | 3Gi | memory | 8Gi | 5 | 50Gi | Burstable |
| alphacar-backup-ns | 10 | cpu | 2CPU | cpu | 6CPU | 5 | 50Gi | Burstable |
| alphacar-backup-ns | 10 | memory | 3Gi | memory | 8Gi | 5 | 50Gi | Burstable |
| alphacar-chaos-ns | 5 | cpu | 1CPU | cpu | 2CPU | - | - | BestEffort |
| alphacar-chaos-ns | 5 | memory | 1Gi | memory | 2Gi | - | - | BestEffort |


## LimitRange (컨테이너 기본/최소/최대 자원)

_원본 시트: `LimitRange` — 61행_

| 이름 | NS | max | max | min | min | default | default | defaultRequest | defaultRequest |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| alphacar-fe-hpa | alphacar-fe-ns | cpu | 500m | cpu | 100m | cpu | 500m | cpu | 100m |
| alphacar-fe-hpa | alphacar-fe-ns | memory | 512Mi | memory | 128Mi | memory | 512Mi | memory | 128Mi |
| alphacar-main-hpa | alphacar-be-ns | cpu | 500m | cpu | 200m | cpu | 500m | cpu | 200m |
| alphacar-main-hpa | alphacar-be-ns | memory | 512Mi | memory | 256Mi | memory | 512Mi | memory | 256Mi |
| alphacar-quote-hpa | alphacar-be-ns | cpu | 500m | cpu | 200m | cpu | 500m | cpu | 200m |
| alphacar-quote-hpa | alphacar-be-ns | memory | 512Mi | memory | 256Mi | memory | 512Mi | memory | 256Mi |
| alphacar-news-hpa | alphacar-be-ns | cpu | 500m | cpu | 200m | cpu | 500m | cpu | 200m |
| alphacar-news-hpa | alphacar-be-ns | memory | 512Mi | memory | 256Mi | memory | 512Mi | memory | 256Mi |
| alphacar-community-hpa | alphacar-be-ns | cpu | 500m | cpu | 200m | cpu | 500m | cpu | 200m |
| alphacar-community-hpa | alphacar-be-ns | memory | 512Mi | memory | 256Mi | memory | 512Mi | memory | 256Mi |
| alphacar-mypage-hpa | alphacar-be-ns | cpu | 500m | cpu | 200m | cpu | 500m | cpu | 200m |
| alphacar-mypage-hpa | alphacar-be-ns | memory | 512Mi | memory | 256Mi | memory | 512Mi | memory | 256Mi |
| alphacar-search-hpa | alphacar-be-ns | cpu | 500m | cpu | 200m | cpu | 500m | cpu | 200m |
| alphacar-search-hpa | alphacar-be-ns | memory | 512Mi | memory | 256Mi | memory | 512Mi | memory | 256Mi |
| alphacar-aichat-hpa | alphacar-be-ns | cpu | 1 CPU | cpu | 300m | cpu | 1 CPU | cpu | 300m |
| alphacar-aichat-hpa | alphacar-be-ns | memory | 1Gi | memory | 256Mi | memory | 1Gi | memory | 256Mi |
| alphacar-mongodb-hpa | alphacar-db-ns | cpu | 2 CPU | cpu | 500Mi | cpu | 2 CPU | cpu | 500Mi |
| alphacar-mongodb-hpa | alphacar-db-ns | memory | 2Gi | memory | 1Gi | memory | 2Gi | memory | 1Gi |
| alphacar-mariadb-hpa | alphacar-db-ns | cpu | 500m | cpu | 200m | cpu | 500m | cpu | 200m |
| alphacar-mariadb-hpa | alphacar-db-ns | memory | 512Mi | memory | 256Mi | memory | 512Mi | memory | 256Mi |
| alphacar-redis-hpa | alphacar-db-ns | cpu | 500m | cpu | 100m | cpu | 500m | cpu | 100m |
| alphacar-redis-hpa | alphacar-db-ns | memory | 512Mi | memory | 128Mi | memory | 512Mi | memory | 128Mi |
| alphacar-alloy-hpa | alphacar-obsv-ns | cpu | 500m | cpu | 100m | cpu | 500m | cpu | 100m |
| alphacar-alloy-hpa | alphacar-obsv-ns | memory | 512Mi | memory | 128Mi | memory | 512Mi | memory | 128Mi |
| alphacar-grafana-hpa | alphacar-obsv-ns | cpu | 500m | cpu | 100m | cpu | 500m | cpu | 100m |
| alphacar-grafana-hpa | alphacar-obsv-ns | memory | 1Gi | memory | 256Mi | memory | 1Gi | memory | 256Mi |
| alphacar-prometheus-hpa | alphacar-obsv-ns | cpu | 2 CPU | cpu | 500Mi | cpu | 2 CPU | cpu | 500Mi |
| alphacar-prometheus-hpa | alphacar-obsv-ns | memory | 4Gi | memory | 1Gi | memory | 4Gi | memory | 1Gi |
| alphacar-loki-hpa | alphacar-obsv-ns | cpu | 1 CPU | cpu | 200m | cpu | 1 CPU | cpu | 200m |
| alphacar-loki-hpa | alphacar-obsv-ns | memory | 2Gi | memory | 512Mi | memory | 2Gi | memory | 512Mi |
| alphacar-tempo-hpa | alphacar-obsv-ns | cpu | 1 CPU | cpu | 200m | cpu | 1 CPU | cpu | 200m |
| alphacar-tempo-hpa | alphacar-obsv-ns | memory | 2Gi | memory | 512Mi | memory | 2Gi | memory | 512Mi |
| alpharcar-jenkins-hpa | alphacar-cicd-ns | cpu | 2 CPU | cpu | 500Mi | cpu | 2 CPU | cpu | 500Mi |
| alpharcar-jenkins-hpa | alphacar-cicd-ns | memory | 2Gi | memory | 1Gi | memory | 2Gi | memory | 1Gi |
| alphacar-sonarqube-hpa | alphacar-cicd-ns | cpu | 2 CPU | cpu | 500Mi | cpu | 2 CPU | cpu | 500Mi |
| alphacar-sonarqube-hpa | alphacar-cicd-ns | memory | 3Gi | memory | 1.5Gi | memory | 3Gi | memory | 1.5Gi |
| alphacar-trivy-hpa | alphacar-cicd-ns | cpu | 1 CPU | cpu | 200m | cpu | 1 CPU | cpu | 200m |
| alphacar-trivy-hpa | alphacar-cicd-ns | memory | 1Gi | memory | 512Mi | memory | 1Gi | memory | 512Mi |
| alphacar-argocd-hpa | alphacar-cicd-ns | cpu | 1 CPU | cpu | 200m | cpu | 1 CPU | cpu | 200m |
| alphacar-argocd-hpa | alphacar-cicd-ns | memory | 1Gi | memory | 512Mi | memory | 1Gi | memory | 512Mi |
| alphacar-harbor-hpa | alphacar-cicd-ns | cpu | 2 CPU | cpu | 500Mi | cpu | 2 CPU | cpu | 500Mi |
| alphacar-harbor-hpa | alphacar-cicd-ns | memory | 4Gi | memory | 1.5Gi | memory | 4Gi | memory | 1.5Gi |
| alphacar-istio-hpa | alphacar-istio-system | cpu | 2 CPU | cpu | 500Mi | cpu | 2 CPU | cpu | 500Mi |
| alphacar-istio-hpa | alphacar-istio-system | memory | 2Gi | memory | 1Gi | memory | 2Gi | memory | 1Gi |
| alphacar-cert-manager-hpa | alphaca-security-system | cpu | 200m | cpu | 50m | cpu | 200m | cpu | 50m |
| alphacar-cert-manager-hpa | alphaca-security-system | memory | 256Mi | memory | 64Mi | memory | 256Mi | memory | 64Mi |
| alphacar-kube-bench-hpa | alphaca-security-system | cpu | - | cpu | - | cpu | - | cpu | - |
| alphacar-kube-bench-hpa | alphaca-security-system | memory | - | memory | - | memory | - | memory | - |
| alphacar-kyverno-hpa | alphaca-security-system | cpu | 512Mi | memory | 256Mi | cpu | 512Mi | cpu | 256Mi |
| alphacar-kyverno-hpa | alphaca-security-system | memory | 500m | cpu | 100m | memory | 500m | memory | 100m |
| alphacar-strimzi-hpa | alphacar-striming-ns | cpu | 500m | cpu | 100m | cpu | 500m | cpu | 100m |
| alphacar-strimzi-hpa | alphacar-striming-ns | memory | 512Mi | memory | 128Mi | memory | 512Mi | memory | 128Mi |
| alphacar-kafka-hpa | alphacar-striming-ns | cpu | 2 CPU | cpu | 500Mi | cpu | 2 CPU | cpu | 500Mi |
| alphacar-kafka-hpa | alphacar-striming-ns | memory | 2Gi | memory | 1Gi | memory | 2Gi | memory | 1Gi |
| alphacar-longhorn-hpa | alphacar-backup-ns | cpu | 2 CPU | cpu | 500Mi | cpu | 2 CPU | cpu | 500Mi |
| alphacar-longhorn-hpa | alphacar-backup-ns | memory | 4Gi | memory | 1.5Gi | memory | 4Gi | memory | 1.5Gi |
| alphacar-velero-hpa | alphacar-backup-ns | cpu | 512Mi | memory | 256Mi | cpu | 512Mi | cpu | 256Mi |
| alphacar-velero-hpa | alphacar-backup-ns | memory | 500m | cpu | 100m | memory | 500m | memory | 100m |
| alphacar-chaos-mesh-hpa | alphacar-chaos-ns | cpu | 512Mi | memory | 256Mi | cpu | 512Mi | cpu | 256Mi |
| alphacar-chaos-mesh-hpa | alphacar-chaos-ns | memory | 500m | cpu | 100m | memory | 500m | memory | 100m |


## HPA (수평 파드 오토스케일러)

_원본 시트: `HPA` — 61행_

| 이름 | NS | kind | kind | replicas | replicas | resource | resource |
| --- | --- | --- | --- | --- | --- | --- | --- |
| alphacar-fe-hpa | alphacar-fe-ns | Deployment | Deployment | min | 3 | cpu | 50 |
| alphacar-fe-hpa | alphacar-fe-ns | Deployment | Deployment | max | 6 | memory | 60 |
| alphacar-main-hpa | alphacar-be-ns | Deployment | Deployment | min | 3 | cpu | 70 |
| alphacar-main-hpa | alphacar-be-ns | Deployment | Deployment | max | 6 | memory | 80 |
| alphacar-quote-hpa | alphacar-be-ns | Deployment | Deployment | min | 3 | cpu | 60 |
| alphacar-quote-hpa | alphacar-be-ns | Deployment | Deployment | max | 6 | memory | 70 |
| alphacar-news-hpa | alphacar-be-ns | Deployment | Deployment | min | 3 | cpu | 60 |
| alphacar-news-hpa | alphacar-be-ns | Deployment | Deployment | max | 6 | memory | 70 |
| alphacar-community-hpa | alphacar-be-ns | Deployment | Deployment | min | 3 | cpu | 50 |
| alphacar-community-hpa | alphacar-be-ns | Deployment | Deployment | max | 6 | memory | 60 |
| alphacar-mypage-hpa | alphacar-be-ns | Deployment | Deployment | min | 3 | cpu | 70 |
| alphacar-mypage-hpa | alphacar-be-ns | Deployment | Deployment | max | 6 | memory | 80 |
| alphacar-search-hpa | alphacar-be-ns | Deployment | Deployment | min | 3 | cpu | 70 |
| alphacar-search-hpa | alphacar-be-ns | Deployment | Deployment | max | 6 | memory | 80 |
| alphacar-aichat-hpa | alphacar-be-ns | Deployment | Deployment | min | 3 | cpu | 70 |
| alphacar-aichat-hpa | alphacar-be-ns | Deployment | Deployment | max | 6 | memory | 80 |
| alphacar-mongodb-hpa | alphacar-db-ns | Statefulset | Statefulset | min | 3 | cpu | 70 |
| alphacar-mongodb-hpa | alphacar-db-ns | Statefulset | Statefulset | max | 3 | memory | 80 |
| alphacar-mariadb-hpa | alphacar-db-ns | Statefulset | Statefulset | min | 1 | cpu | 70 |
| alphacar-mariadb-hpa | alphacar-db-ns | Statefulset | Statefulset | max | 1 | memory | 80 |
| alphacar-redis-hpa | alphacar-db-ns | Statefulset | Statefulset | min | 1 | cpu | 70 |
| alphacar-redis-hpa | alphacar-db-ns | Statefulset | Statefulset | max | 1 | memory | 80 |
| alphacar-alloy-hpa | alphacar-obsv-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-alloy-hpa | alphacar-obsv-ns | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-grafana-hpa | alphacar-obsv-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-grafana-hpa | alphacar-obsv-ns | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-prometheus-hpa | alphacar-obsv-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-prometheus-hpa | alphacar-obsv-ns | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-loki-hpa | alphacar-obsv-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-loki-hpa | alphacar-obsv-ns | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-tempo-hpa | alphacar-obsv-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-tempo-hpa | alphacar-obsv-ns | Deployment | Deployment | max | 1 | memory | 80 |
| alpharcar-jenkins-hpa | alphacar-cicd-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alpharcar-jenkins-hpa | alphacar-cicd-ns | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-sonarqube-hpa | alphacar-cicd-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-sonarqube-hpa | alphacar-cicd-ns | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-trivy-hpa | alphacar-cicd-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-trivy-hpa | alphacar-cicd-ns | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-argocd-hpa | alphacar-cicd-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-argocd-hpa | alphacar-cicd-ns | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-harbor-hpa | alphacar-cicd-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-harbor-hpa | alphacar-cicd-ns | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-istio-hpa | alphacar-istio-system | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-istio-hpa | alphacar-istio-system | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-cert-manager-hpa | alphaca-security-system | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-cert-manager-hpa | alphaca-security-system | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-kube-bench-hpa | alphaca-security-system | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-kube-bench-hpa | alphaca-security-system | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-kyverno-hpa | alphaca-security-system | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-kyverno-hpa | alphaca-security-system | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-strimzi-hpa | alphacar-striming-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-strimzi-hpa | alphacar-striming-ns | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-kafka-hpa | alphacar-striming-ns | Deployment | Deployment | min | 3 | cpu | 70 |
| alphacar-kafka-hpa | alphacar-striming-ns | Deployment | Deployment | max | 3 | memory | 80 |
| alphacar-longhorn-hpa | alphacar-backup-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-longhorn-hpa | alphacar-backup-ns | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-velero-hpa | alphacar-backup-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-velero-hpa | alphacar-backup-ns | Deployment | Deployment | max | 1 | memory | 80 |
| alphacar-chaos-mesh-hpa | alphacar-chaos-ns | Deployment | Deployment | min | 1 | cpu | 70 |
| alphacar-chaos-mesh-hpa | alphacar-chaos-ns | Deployment | Deployment | max | 1 | memory | 80 |


## Liveness / Readiness Probe

_원본 시트: `Liveness Endpoint & Readiness E` — 54행_

| Deploy 명 | 항목 | Liveness Probe 설정 | Readiness Probe 설정 | 비고 | claimName |
| --- | --- | --- | --- | --- | --- |
| frontend | 엔드포인트 | / | / |  |  |
|  | 포트 | 5174 | 5174 | 프론트엔드 서비스 전용 포트 |  |
|  | initialDelaySeconds | 5초 | 5초 | 컨테이너 시작 후 첫 헬스체크 실행 전 대기 시간 |  |
|  | periodSeconds | 10초 | 5초 |  |  |
|  | timeoutSeconds | 3초 | 2초 | 응답 대기 시간 (응답이 없으면 실패로 판단) |  |
|  | failureThreshold | 3회 연속 실패 | 3회 연속 실패 | 연속 실패 시 해당 컨테이너 재시작 또는 트래픽 전달 제외 | 연속 실패 시 해당 컨테이너 재시작 또는 트래픽 전달 제외 |
| main-backend | 엔드포인트 | /healthz | /ready | /healthz은 단순 애플리케이션 상태 확인, /ready는 서비스 준비 상태 확인 | /healthz은 단순 애플리케이션 상태 확인, /ready는 서비스 준비 상태 확인 |
|  | 포트 | 3001 | 3001 | 백엔드 인증 서비스 전용 포트 |  |
|  | initialDelaySeconds | 5초 | 5초 | 컨테이너 시작 후 초기 헬스체크 지연 시간 |  |
|  | periodSeconds | 1800초 | 1800초 |  |  |
|  | timeoutSeconds | 5초 | 5초 | 응답 지연 시 최대 대기 시간 |  |
|  | failureThreshold | 3회 연속 실패 | 3회 연속 실패 | 연속 실패 횟수 후 컨테이너 재시작 혹은 트래픽 제외 | 연속 실패 횟수 후 컨테이너 재시작 혹은 트래픽 제외 |
| news-backend | 엔드포인트 | /healthz | /ready |  |  |
|  | 포트 | 3002 | 3002 | 백엔드 검색 서비스 전용 포트 |  |
|  | initialDelaySeconds | 5초 | 5초 | 초기 부팅 및 API 준비 시간 고려 |  |
|  | periodSeconds | 30초 | 20초 | Liveness는 10초, Readiness는 5초 주기로 검사 |  |
|  | timeoutSeconds | 5초 | 5초 | 네트워크 지연을 고려한 응답 대기 시간 |  |
|  | failureThreshold | 3회 연속 실패 | 3회 연속 실패 | 일정 횟수 실패 시 재시작 또는 서비스 제외 |  |
| Gyeonjeok-backend | 엔드포인트 | /healthz | /ready |  |  |
|  | 포트 | 3003 | 3003 | 백엔드 가사 서비스 전용 포트 |  |
|  | initialDelaySeconds | 5초 | 5초 | 컨테이너 시작 후 초기 상태 체크 시간 |  |
|  | periodSeconds | 30초 | 20초 | 상태 점검 주기 |  |
|  | timeoutSeconds | 5초 | 5초 | 응답 지연 시 허용 시간 |  |
|  | failureThreshold | 3회 연속 실패 | 3회 연속 실패 | 연속 실패 시 재시작/트래픽 차단 |  |
| community-backend | 엔드포인트 | /healthz | /ready |  |  |
|  | 포트 | 3004 | 3004 | 백엔드 번역 서비스 전용 포트 |  |
|  | initialDelaySeconds | 5초 | 5초 | 초기 부팅 및 의존성 연결 확인 시간 |  |
|  | periodSeconds | 30초 | 20초 | 상태 점검 간격 |  |
|  | timeoutSeconds | 5초 | 5초 | 응답 대기 시간 |  |
|  | failureThreshold | 3회 연속 실패 | 3회 연속 실패 | 연속 실패 시 자동 복구 |  |
| search-backend | 엔드포인트 | /healthz | /ready |  |  |
|  | 포트 | 3005 | 3005 | 백엔드 플레이리스트 서비스 전용 포트 |  |
|  | initialDelaySeconds | 5초 | 5초 | 컨테이너 시작 후 최초 상태 체크 |  |
|  | periodSeconds | 60초 | 30초 | 주기적인 상태 체크 |  |
|  | timeoutSeconds | 5초 | 5초 | 응답 허용 최대 시간 |  |
|  | failureThreshold | 3회 연속 실패 | 3회 연속 실패 | 연속 실패 시 적절한 조치 (재시작/트래픽 차단) |  |
| mypage-backend | 엔드포인트 | /healthz | /ready |  |  |
|  | 포트 | 3005 | 3005 | 백엔드 플레이리스트 서비스 전용 포트 |  |
|  | initialDelaySeconds | 5초 | 5초 | 컨테이너 시작 후 최초 상태 체크 |  |
|  | periodSeconds | 60초 | 30초 | 주기적인 상태 체크 |  |
|  | timeoutSeconds | 5초 | 5초 | 응답 허용 최대 시간 |  |
|  | failureThreshold | 3회 연속 실패 | 3회 연속 실패 | 연속 실패 시 적절한 조치 (재시작/트래픽 차단) |  |
| aichat-backend | 엔드포인트 | /healthz | /ready |  |  |
|  | 포트 | 3005 | 3005 | 백엔드 플레이리스트 서비스 전용 포트 |  |
|  | initialDelaySeconds | 5초 | 5초 | 컨테이너 시작 후 최초 상태 체크 |  |
|  | periodSeconds | 60초 | 30초 | 주기적인 상태 체크 |  |
|  | timeoutSeconds | 5초 | 5초 | 응답 허용 최대 시간 |  |
|  | failureThreshold | 3회 연속 실패 | 3회 연속 실패 | 연속 실패 시 적절한 조치 (재시작/트래픽 차단) |  |
|  | 설명 | 예시 기준 |  |  |  |
| initialDelaySeconds | 컨테이너 시작 후 최초 Probe 실행까지 대기하는 시간 | 애플리케이션 초기화에 10초 소요 시 → 10초 이상 | 애플리케이션 초기화에 10초 소요 시 → 10초 이상 |  |  |
| periodSeconds | Probe를 주기적으로 실행하는 간격 | 빠른 감지가 필요하면 510초, 그렇지 않으면 1015초 | 빠른 감지가 필요하면 510초, 그렇지 않으면 1015초 |  |  |
| timeoutSeconds | Probe 응답을 기다리는 최대 시간 | API 응답이 1초 내에 오면 → 2~3초 |  |  |  |
| failureThreshold | 연속 실패 후 컨테이너를 비정상으로 간주하는 실패 횟수 | 일시적 오류를 고려해 2~3회 실패 시 재시작 |  |  |  |


## Deployments (워크로드)

_원본 시트: `Deployments` — 61행_

| NS | Replicas | label | label | image | containerPort | configmapRef | secretRef | claimName | requests | requests | limits | limits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| alphacar-fe-ns | 3 | frontend | layout | alphacar-fe | 80 | alphacar-ui.conf |  |  | cpu | 100m | cpu | 500m |
| alphacar-fe-ns | 3 | frontend | layout | alphacar-fe | 80 | alphacar-ui.conf |  |  | memory | 512Mi | memory | 1Gi |
| alphacar-be-ns | 3 | backend | main | alphacar-main | 3002 | alphacar-main .conf |  |  | cpu | 200M | cpu | 500m |
| alphacar-be-ns | 3 | backend | main | alphacar-main | 3002 | alphacar-main .conf |  |  | memory | 256Mi | memory | 512Mi |
| alphacar-be-ns | 3 | backend | quote | alphacar-quote | 3003 | alphacar-quote.conf |  |  | cpu | 200M | cpu | 500m |
| alphacar-be-ns | 3 | backend | quote | alphacar-quote | 3003 | alphacar-quote.conf |  |  | memory | 256Mi | memory | 512Mi |
| alphacar-be-ns | 3 | backend | news | alphacar-news | 3004 | alphacar-drive.conf |  |  | cpu | 200M | cpu | 500m |
| alphacar-be-ns | 3 | backend | news | alphacar-news | 3004 | alphacar-drive.conf |  |  | memory | 256Mi | memory | 512Mi |
| alphacar-be-ns | 3 | backend | community | alphacar-community | 3005 | alphacar-community.conf |  |  | cpu | 200M | cpu | 500m |
| alphacar-be-ns | 3 | backend | community | alphacar-community | 3005 | alphacar-community.conf |  |  | memory | 256Mi | memory | 512Mi |
| alphacar-be-ns | 3 | backend | mypage | alphacar-mypage | 3006 | alphacar-mypage.conf |  |  | cpu | 200M | cpu | 500m |
| alphacar-be-ns | 3 | backend | mypage | alphacar-mypage | 3006 | alphacar-mypage.conf |  |  | memory | 256Mi | memory | 512Mi |
| alphacar-be-ns | 3 | backend | search | alphacar-search | 3007 | alphacar-search.conf |  |  | cpu | 200M | cpu | 500m |
| alphacar-be-ns | 3 | backend | search | alphacar-search | 3007 | alphacar-search.conf |  |  | memory | 256Mi | memory | 512Mi |
| alphacar-be-ns | 3 | backend | aichat | alphacar-aichat | 3008 | alphacar-aichat.conf |  |  | cpu | 200M | cpu | 500m |
| alphacar-be-ns | 3 | backend | aichat | alphacar-aichat | 3008 | alphacar-aichat.conf |  |  | memory | 256Mi | memory | 512Mi |
| alphacar-db-ns | 1 | database | redis | alphacar-redis | 6379 | redis.conf |  |  | cpu | 500Mi | cpu | 500Mi |
| alphacar-db-ns | 1 | database | redis | alphacar-redis | 6379 | redis.conf |  |  | memory | 1Gi | memory | 1Gi |
| alphacar-db-ns | 3 | database | mongo | alphacar-mongo | 27017 | mongo.conf | mongo-secret |  | cpu | 500Mi | cpu | 500Mi |
| alphacar-db-ns | 3 | database | mongo | alphacar-mongo | 27017 | mongo.conf | mongo-secret |  | memory | 1Gi | memory | 1Gi |
| alphacar-db-ns | 1 | database | maria | alphacar-maria | 3306 | maria.conf | maria-secret |  | cpu | 500Mi | cpu | 500Mi |
| alphacar-db-ns | 1 | database | maria | alphacar-maria | 3306 | maria.conf | maria-secret |  | memory | 1Gi | memory | 1Gi |
| alphacar-obsv-ns | 1 | monitoring | log | loki | 3100 | loki.conf |  |  | cpu | 200m | cpu | 1 CPU |
| alphacar-obsv-ns | 1 | monitoring | log | loki | 3100 | loki.conf |  |  | memory | 512Mi | memory | 2Gi |
| alphacar-obsv-ns | 1 | monitoring | metric | prometheus | 9090 | prometheus.conf |  |  | cpu | 500Mi | cpu | 2 CPU |
| alphacar-obsv-ns | 1 | monitoring | metric | prometheus | 9090 | prometheus.conf |  |  | memory | 1Gi | memory | 4Gi |
| alphacar-obsv-ns | 1 | monitoring | dashboard | grafana | 3000 | grafana.conf |  |  | cpu | 100m | cpu | 500m |
| alphacar-obsv-ns | 1 | monitoring | dashboard | grafana | 3000 | grafana.conf |  |  | memory | 256Mi | memory | 1Gi |
| alphacar-obsv-ns | 1 | monitoring | alloy | grafana alloy | 12345 | grafana-alloy.conf |  |  | cpu | 100m | cpu | 500m |
| alphacar-obsv-ns | 1 | monitoring | alloy | grafana alloy | 12345 | grafana-alloy.conf |  |  | memory | 128Mi | memory | 512Mi |
| alphacar-obsv-ns | 1 | monitoring | trace | tempo | 3200 | tempo.conf |  |  | cpu | 200m | cpu | 1 CPU |
| alphacar-obsv-ns | 1 | monitoring | trace | tempo | 3200 | tempo.conf |  |  | memory | 512Mi | memory | 2Gi |
| alphacar-cicd-ns | 1 | cicd | jenkins | jenkins | 8080 | jenkins.conf |  |  | cpu | 500Mi | cpu | 2 CPU |
| alphacar-cicd-ns | 1 | cicd | jenkins | jenkins | 8080 | jenkins.conf |  |  | memory | 1Gi | memory | 2Gi |
| alphacar-cicd-ns | 1 | cicd | sonarqube | sonarqube | 9000 | sonarqube.conf |  |  | cpu | 500Mi | cpu | 2 CPU |
| alphacar-cicd-ns | 1 | cicd | sonarqube | sonarqube | 9000 | sonarqube.conf |  |  | memory | 1.5Gi | memory | 3Gi |
| alphacar-cicd-ns | 1 | cicd | trivy | trivy | 8080 |  |  |  | cpu | 200m | cpu | 1 CPU |
| alphacar-cicd-ns | 1 | cicd | trivy | trivy | 8080 |  |  |  | memory | 512Mi | memory | 1Gi |
| alphacar-cicd-ns | 1 | cicd | argoCD | argoCD | 8080 |  | argocd-secret |  | cpu | 200m | cpu | 1 CPU |
| alphacar-cicd-ns | 1 | cicd | argoCD | argoCD | 8080 |  | argocd-secret |  | memory | 512Mi | memory | 1Gi |
| alphacar-cicd-ns | 1 | cicd | harbor | harbor | 8080 | harbor.conf | harbor-secret |  | cpu | 500Mi | cpu | 2 CPU |
| alphacar-cicd-ns | 1 | cicd | harbor | harbor | 8080 | harbor.conf | harbor-secret |  | memory | 1.5Gi | memory | 4Gi |
| alphacar-istio-system | 1 | network | istio | istio |  | istio-mesh.conf |  |  | cpu | 500Mi | cpu | 2 CPU |
| alphacar-istio-system | 1 | network | istio | istio |  | istio-mesh.conf |  |  | memory | 1Gi | memory | 2Gi |
| alphaca-security-system | 1 | security | cert-manager | cert-manager |  | cert-manager.conf |  |  | cpu | 50m | cpu | 200m |
| alphaca-security-system | 1 | security | cert-manager | cert-manager |  | cert-manager.conf |  |  | memory | 64Mi | memory | 256Mi |
| alphaca-security-system | 1 | security | kube-bench | kube-bench |  |  |  |  | cpu | - | cpu | - |
| alphaca-security-system | 1 | security | kube-bench | kube-bench |  |  |  |  | memory | - | memory | - |
| alphaca-security-system | 1 | security | kyverno | kyverno |  | kyverno.conf |  |  | cpu | 256Mi | cpu | 512Mi |
| alphaca-security-system | 1 | security | kyverno | kyverno |  | kyverno.conf |  |  | memory | 100m | memory | 500m |
| alphacar-striming-ns | 1 | data | strimzi | strimzi |  | strimzi-operator.conf |  |  | cpu | 100m | cpu | 500m |
| alphacar-striming-ns | 1 | data | strimzi | strimzi |  | strimzi-operator.conf |  |  | memory | 128Mi | memory | 512Mi |
| alphacar-striming-ns | 3 | data | kafka | kafka | 9092 | kafka.conf | kafka-secret |  | cpu | 500Mi | cpu | 2 CPU |
| alphacar-striming-ns | 3 | data | kafka | kafka | 9092 | kafka.conf | kafka-secret |  | memory | 1Gi | memory | 2Gi |
| alphacar-backup-ns | 1 | data | longhorn | longhorn |  | nook.conf |  |  | cpu | 500Mi | cpu | 2 CPU |
| alphacar-backup-ns | 1 | data | longhorn | longhorn |  | nook.conf |  |  | memory | 1.5Gi | memory | 4Gi |
| alphacar-backup-ns | 1 | data | velero | velero |  | velero.conf | velero-secret |  | cpu | 256Mi | cpu | 512Mi |
| alphacar-backup-ns | 1 | data | velero | velero |  | velero.conf | velero-secret |  | memory | 100m | memory | 500m |
| alphacar-chaos-ns | 1 | chaos | chaos mesh | chaos mesh |  | chaos-mesh.conf |  |  | cpu | 256Mi | cpu | 512Mi |
| alphacar-chaos-ns | 1 | chaos | chaos mesh | chaos mesh |  | chaos-mesh.conf |  |  | memory | 100m | memory | 500m |


## StatefulSet

_원본 시트: `Statefulset` — 3행_

| NS | Replicas | label | image | containerPort | configmapRef | secretRef | claimName | requests | limits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| alphacar-db-ns | 3 | app=alphacar-mongo | mongo:8.0 | 27017 |  |  | alphacar-mongo-data | memory=512Mi,cpu=250m | memory=1Gi,cpu=500m |
| alphacar-ek-ns | 1 | app=alphacar-elasticsearch | docker.elastic.co/elasticsearch/elasticsearch:8.11.0 | 9200 | alphacar-elasticsearch-config | alphacar-elasticsearch-config | elasticsearch-data | memory=1Gi,cpu=500m | memory=1.5Gi,cpu=1000m |


## PodSecurity (Pod Security Standards)

_원본 시트: `PodSecurity` — 13행_

| NS | pod | PodSecurityLevel | RunAsNonRoot | ReadOnlyRootFilesystem | SeccompProfile |
| --- | --- | --- | --- | --- | --- |
| alphacar-be-ns | alphacar-main | Restricted | True | True | RuntimeDefault |
| alphacar-be-ns | alphacar-quote | Restricted | True | True | RuntimeDefault |
| alphacar-be-ns | alphacar-community | Restricted | True | True | RuntimeDefault |
| alphacar-be-ns | alphacar-mypage | Restricted | True | True | RuntimeDefault |
| alphacar-be-ns | alphacar-search | Restricted | True | True | RuntimeDefault |
| alphacar-be-ns | alphacar-news | Restricted | True | True | RuntimeDefault |
| alphacar-be-ns | alphacar-aichat | Restricted | True | True | RuntimeDefault |
| alphacar-fe-ns | alphacar-fe | Restricted | True | True | RuntimeDefault |
| alphacar-istio-system | alphacar-istio | Restricted | True | True | RuntimeDefault |
| alphacar-db-ns | alphacar-mongo | Baseline | False | False | RuntimeDefault |
| alphacar-ek-ns | alphacar-elasticsearch | Baseline | True | False | RuntimeDefault |
| alphacar-ek-ns | alphacar-kibana | Restricted | True | True | RuntimeDefault |


## Service

_원본 시트: `SVC` — 62행_

| NS | pod | port | targetPort | type | type |
| --- | --- | --- | --- | --- | --- |
| alphacar-fe-ns | alphacar-fe | 80 | 80 | ClusterIP |  |
| alphacar-fe-ns | alphacar-fe | 80 | 80 | ClusterIP |  |
| alphacar-be-ns | alphacar-main-be | 3002 | 3002 | ClusterIP |  |
| alphacar-be-ns | alphacar-main-be | 3002 | 3002 | ClusterIP |  |
| alphacar-be-ns | alphacar-quote-be | 3003 | 3003 | ClusterIP |  |
| alphacar-be-ns | alphacar-quote-be | 3003 | 3003 | ClusterIP |  |
| alphacar-be-ns | alphacar-news-be | 3004 | 3004 | ClusterIP |  |
| alphacar-be-ns | alphacar-news-be | 3004 | 3004 | ClusterIP |  |
| alphacar-be-ns | alphacar-community-be | 3005 | 3005 | ClusterIP |  |
| alphacar-be-ns | alphacar-community-be | 3005 | 3005 | ClusterIP |  |
| alphacar-be-ns | alphacar-mypage-be | 3006 | 3006 | ClusterIP |  |
| alphacar-be-ns | alphacar-mypage-be | 3006 | 3006 | ClusterIP |  |
| alphacar-be-ns | alphacar-search-be | 3007 | 3007 | ClusterIP |  |
| alphacar-be-ns | alphacar-search-be | 3007 | 3007 | ClusterIP |  |
| alphacar-be-ns | alphacar-aichat-be | 3008 | 3008 | ClusterIP |  |
| alphacar-be-ns | alphacar-aichat-be | 3008 | 3008 | ClusterIP |  |
| alphacar-db-ns | alphacar-redis | 6379 | 6379 | ClusterIP |  |
| alphacar-db-ns | alphacar-redis | 6379 | 6379 | ClusterIP |  |
| alphacar-db-ns | alphacar-mongo | 27017 | 27017 | ClusterIP |  |
| alphacar-db-ns | alphacar-mongo | 27017 | 27017 | ClusterIP |  |
| alphacar-db-ns | alphacar-maria | 3306 | 3306 | ClusterIP |  |
| alphacar-db-ns | alphacar-maria | 3306 | 3306 | ClusterIP |  |
| alphacar-obsv-ns | loki | 3100 | 3100 | ClusterIP |  |
| alphacar-obsv-ns | loki | 3100 | 3100 | ClusterIP |  |
| alphacar-obsv-ns | prometheus | 9090 | 9090 | ClusterIP |  |
| alphacar-obsv-ns | prometheus | 9090 | 9090 | ClusterIP |  |
| alphacar-obsv-ns | grafana | 3000 | 3000 | ClusterIP |  |
| alphacar-obsv-ns | grafana | 3000 | 3000 | ClusterIP |  |
| alphacar-obsv-ns | grafana alloy | 12345 | 12345 | ClusterIP |  |
| alphacar-obsv-ns | grafana alloy | 12345 | 12345 | ClusterIP |  |
| alphacar-obsv-ns | tempo | 3200 | 3200 | ClusterIP |  |
| alphacar-obsv-ns | tempo | 3200 | 3200 | ClusterIP |  |
| alphacar-cicd-ns | jenkins | 32000 | 8080 | ClusterIP |  |
| alphacar-cicd-ns | jenkins | 32000 | 8080 | ClusterIP |  |
| alphacar-cicd-ns | sonarqube | 32001 | 9000 | ClusterIP |  |
| alphacar-cicd-ns | sonarqube | 32001 | 9000 | ClusterIP |  |
| alphacar-cicd-ns | sonarqube | 32001 | 9000 | ClusterIP |  |
| alphacar-cicd-ns | trivy | 8080 | 8080 | ClusterIP |  |
| alphacar-cicd-ns | trivy | 8080 | 8080 | ClusterIP |  |
| alphacar-cicd-ns | argoCD | 30001 | 8080 | ClusterIP |  |
| alphacar-cicd-ns | argoCD | 30001 | 8080 | ClusterIP |  |
| alphacar-cicd-ns | harbor | 30002 | 8080 | ClusterIP |  |
| alphacar-cicd-ns | harbor | 30002 | 8080 | ClusterIP |  |
| alphacar-istio-system | istio |  |  | ClusterIP |  |
| alphacar-istio-system | istio |  |  | ClusterIP |  |
| alphaca-security-system | cert-manager |  |  | ClusterIP |  |
| alphaca-security-system | cert-manager |  |  | ClusterIP |  |
| alphaca-security-system | kube-bench |  |  | ClusterIP |  |
| alphaca-security-system | kube-bench |  |  | ClusterIP |  |
| alphaca-security-system | kyverno | 8000 | 8000 | ClusterIP |  |
| alphaca-security-system | kyverno | 8000 | 8000 | ClusterIP |  |
| alphacar-striming-ns | strimzi |  |  | ClusterIP |  |
| alphacar-striming-ns | strimzi |  |  | ClusterIP |  |
| alphacar-striming-ns | kafka | 9092 | 9092 | ClusterIP |  |
| alphacar-striming-ns | kafka | 9092 | 9092 | ClusterIP |  |
| alphacar-backup-ns | longhorn | 9500 | 9500 | ClusterIP |  |
| alphacar-backup-ns | longhorn | 9500 | 9500 | ClusterIP |  |
| alphacar-backup-ns | velero |  |  | ClusterIP |  |
| alphacar-backup-ns | velero |  |  | ClusterIP |  |
| alphacar-chaos-ns | chaos mesh |  |  | ClusterIP |  |
| alphacar-chaos-ns | chaos mesh |  |  | ClusterIP |  |


## ConfigMap

_원본 시트: `ConfigMap` — 25행_

| 이름 | NS | key | value |
| --- | --- | --- | --- |
| alphacar-be-config | alphacar-be-ns | MONGO_HOST | alphacar-mongo.alphacar-db-ns.svc.cluster.local |
| alphacar-be-config | alphacar-be-ns | MONGO_PORT | 27017 |
| alphacar-be-config | alphacar-be-ns | MONGO_USER | triple_user |
| alphacar-be-config | alphacar-be-ns | MONGO_PASS | triple_password |
| alphacar-be-config | alphacar-be-ns | MONGO_DB_NAME | triple_db |
| alphacar-be-config | alphacar-be-ns | MONGO_USER_AICHAT | proj |
| alphacar-be-config | alphacar-be-ns | MONGO_PASS_AICHAT | pass123 |
| alphacar-be-config | alphacar-be-ns | MONGODB_URI | mongodb://triple_user:triple_password@... |
| alphacar-be-config | alphacar-be-ns | REDIS_HOST | 192.168.0.175 |
| alphacar-be-config | alphacar-be-ns | REDIS_PORT | 6379 |
| alphacar-be-config | alphacar-be-ns | MARIADB_HOST | 211.46.52.151 |
| alphacar-be-config | alphacar-be-ns | MARIADB_PORT | 15432 |
| alphacar-be-config | alphacar-be-ns | MARIADB_USER | team1 |
| alphacar-be-config | alphacar-be-ns | MARIADB_PASS | Gkrtod1@ |
| alphacar-be-config | alphacar-be-ns | MARIADB_DB_NAME | team1 |
| alphacar-be-config | alphacar-ek-ns | ELASTICSEARCH_URL | http://alphacar-elasticsearch.alphacar-obsv-ns.svc.cluster.local:9200 |
| alphacar-nginx-config | alphacar-fe-ns | nginx.conf | (nginx 설정 파일) |
| alphacar-elasticsearch-config | alphacar-ek-ns | elasticsearch.yml | (elasticsearch 설정) |
| alphacar-alloy-config | alphacar-obsv-ns | config.alloy | (alloy 설정 파일) |
| alphacar-monstache-config | alphacar-ek-ns | config.toml | (monstache 설정 파일) |
| harbor-ca-cert | alphacar-cicd-ns | ca.crt | (CA 인증서) |
| alphacar-env | alphacar-be-ns | OTEL_EXPORTER_OTLP_ENDPOINT | http://alloy-agent:4317 |
| alphacar-env | alphacar-be-ns | MONGO_HOST | mongodb-0.mongodb-headless.alphacar.svc.cluster.local |
| alphacar-env | alphacar-be-ns | MONGO_PORT | 27017 |


## Secret

_원본 시트: `Secret` — 37행_

| 이름 | NS | key | value | type | Sealed-secret |
| --- | --- | --- | --- | --- | --- |
| alphacar-mongo-secret | alphacar-db-ns | username | triple_user | Opaque |  |
| alphacar-mongo-secret | alphacar-db-ns | password | triple_password | Opaque |  |
| alphacar-mongo-secret | alphacar-db-ns | host | alphacar-mongo.alphacar-db-ns.svc.cluster.local | Opaque |  |
| alphacar-mongo-secret | alphacar-db-ns | port | 27017 | Opaque |  |
| alphacar-mongo-secret | alphacar-db-ns | database | triple_db | Opaque |  |
| alphacar-mongo-aichat-secret | alphacar-db-ns | username | proj | Opaque |  |
| alphacar-mongo-aichat-secret | alphacar-db-ns | password | pass123 | Opaque |  |
| alphacar-mongo-aichat-secret | alphacar-db-ns | host | alphacar-mongo.alphacar-db-ns.svc.cluster.local | Opaque |  |
| alphacar-mongo-aichat-secret | alphacar-db-ns | port | 27017 | Opaque |  |
| alphacar-mongo-aichat-secret | alphacar-db-ns | database | triple_db | Opaque |  |
| alphacar-redis-secret | alphacar-db-ns | password | k8spass# | Opaque |  |
| alphacar-redis-secret | alphacar-db-ns | host | 192.168.0.175 | Opaque |  |
| alphacar-redis-secret | alphacar-db-ns | port | 6379 | Opaque |  |
| alphacar-maria-secret | alphacar-db-ns | username | team1 | Opaque |  |
| alphacar-maria-secret | alphacar-db-ns | password | Gkrtod1@ | Opaque |  |
| alphacar-maria-secret | alphacar-db-ns | host | 211.46.52.151 | Opaque |  |
| alphacar-maria-secret | alphacar-db-ns | port | 15432 | Opaque |  |
| alphacar-maria-secret | alphacar-db-ns | database | team1 | Opaque |  |
| alphacar-jwt-secret | alphacar-db-ns | secret | JWT_KEY | Opaque |  |
| harbor-registry-secret | alphacar | .dockerconfigjson | (docker config) | kubernetes.io/dockerconfigjson |  |
| ssl-cert | alphacar | nginx.crt | (SSL 인증서) | Opaque |  |
| ssl-cert | alphacar | nginx.key | (SSL 키) | Opaque |  |
| minio-credentials | minio | MINIO_ROOT_USER | minioadmin | Opaque |  |
| minio-credentials | minio | MINIO_ROOT_PASSWORD | minioadmin123 | Opaque |  |
| mongodb-aichat-secret | alphacar-be-ns | username | proj | Opaque |  |
| mongodb-aichat-secret | alphacar-be-ns | password | pass123 | Opaque |  |
| mongodb-aichat-secret | alphacar-be-ns | host | mongodb-0.mongodb-headless.alphacar.svc.cluster.local | Opaque |  |
| mongodb-aichat-secret | alphacar-be-ns | port | 27017 | Opaque |  |
| mongodb-aichat-secret | alphacar-be-ns | database | triple_db | Opaque |  |
| aws-bedrock-secret | alphacar-be-ns | region | us-east-1 | Opaque |  |
| aws-bedrock-secret | alphacar-be-ns | access_key_id | AKIAVR45…(마스킹됨) | Opaque |  |
| aws-bedrock-secret | alphacar-be-ns | secret_access_key | JgEe…(마스킹됨: 원본 엑셀 참조) | Opaque |  |
| aws-bedrock-secret | alphacar-be-ns | guardrail_id | nfdfeln14bg7 | Opaque |  |
| aws-bedrock-secret | alphacar-be-ns | guardrail_version | DRAFT | Opaque |  |
| aws-bedrock-secret | alphacar-be-ns | embedding_model_id | amazon.titan-embed-text-v2:0 | Opaque |  |
| aws-bedrock-secret | alphacar-be-ns | llm_model_id | meta.llama3-3-70b-instruct-v1:0 | Opaque |  |


## RBAC (ServiceAccount / Role / Binding)

_원본 시트: `Role` — 13행_

| NS | ServiceAccount | Role | RoleBinding | ClusterRole | ClusterRoleBinding | apiGroups | Resource | verbs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| alphacar-be-ns | alphacar-main-sa | alphacar-backend-reader | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | configmaps,secrets | get,list,watch |
| alphacar-be-ns | alphacar-quote-sa | alphacar-backend-reader | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | configmaps,secrets | get,list,watch |
| alphacar-be-ns | alphacar-news-sa | alphacar-backend-reader | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | configmaps,secrets | get,list,watch |
| alphacar-be-ns | alphacar-community-sa | alphacar-backend-reader | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | configmaps,secrets | get,list,watch |
| alphacar-be-ns | alphacar-mypage-sa | alphacar-backend-reader | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | configmaps,secrets | get,list,watch |
| alphacar-be-ns | alphacar-search-sa | alphacar-backend-reader | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | configmaps,secrets | get,list,watch |
| alphacar-be-ns | alphacar-aichat-sa | alphacar-backend-reader | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | alphacar-backend-reader-binding | configmaps,secrets | get,list,watch |
| alphacar-db-ns | alphacar-mongo-sa | alphacar-db-reader | alphacar-db-reader-binding | alphacar-db-reader-binding | alphacar-db-reader-binding |  | configmaps,secrets | get,list,watch |
| alphacar-obsv-ns | alphacar-alloy-sa | alphacar-alloy-reader | alphacar-alloy-reader-binding | alphacar-alloy-reader-binding | alphacar-alloy-reader-binding |  | pods,services,endpoints | get,list,watch |
| alphacar-obsv-ns | alphacar-alloy-sa | alphacar-alloy-sa |  | alphacar-alloy-cluster-reader | alphacar-alloy-cluster-reader-binding | ,apps | pods,services,endpoints,deployments,statefulsets | get,list,watch |
| alphacar-fe-ns | alphacar-fe-sa | alphacar-fe-sa |  |  |  |  |  |  |
| alphacar-fe-ns | alphacar-traefik | alphacar-traefik |  | alphacar-traefik | alphacar-traefik | ,networking.k8s.io,discovery.k8s.io | services,endpoints,secrets,ingresses,ingressclasses,endpointslices,nodes | get,list,watch |


## NetworkPolicy

_원본 시트: `NetworkPolicy` — 5행_

| NS | name | policyTypes | Key | Value |
| --- | --- | --- | --- | --- |
| alphacar-fe-ns | alphacar-fe-deny-all | Ingress,Egress | namespaceSelector | name=alphacar-be-ns (egress to ports 3002,3003,3005,3006,3007,3008,4000); name=kube-system (egress to port 53 UDP,443 TCP); ingress from all (external access) |
| alphacar-be-ns | alphacar-be-deny-all | Ingress,Egress | namespaceSelector | name=alphacar-fe-ns (ingress to ports 3002,3003,3005,3006,3007,3008,4000); name=alphacar-db-ns (egress to port 27017); name=kube-system (egress to port 53 UDP) |
| alphacar-db-ns | alphacar-db-deny-all | Ingress,Egress | namespaceSelector,podSelector | name=alphacar-be-ns (ingress to port 27017); app.kubernetes.io/component=database (ingress/egress to port 27017 for replica set); name=kube-system (egress to port 53 UDP) |
| alphacar-obsv-ns | alphacar-obsv-deny-all | Ingress,Egress | namespaceSelector,podSelector | app.kubernetes.io/component=observability (ingress to port 9200); name=alphacar-be-ns (egress to ports 3002,3003,3005,3006,3007,3008,4000); app=alphacar-elasticsearch (egress to port 9200); name=kube-system (egress to port 53 UDP) |


## PersistentVolumeClaim

_원본 시트: `PVC` — 4행_

| NS | Name | Kind | AccessModes | Storage | StorageClassName |
| --- | --- | --- | --- | --- | --- |
| alphacar-db-ns | alphacar-mongo-data | PersistentVolumeClaim | ReadWriteOnce | 20Gi | longhorn |
| alphacar-db-ns | alphacar-maria-data | PersistentVolumeClaim | ReadWriteOnce | 20Gi | longhorn |
| alphacar-be-ns | aichat-vector-store-pvc | PersistentVolumeClaim | ReadWriteOnce | 10Gi | - |


## PersistentVolume

_원본 시트: `PV` — 3행_

| Name | Kind | Provisioner | ReplicaCount | CstorPoolCluster | CasType | AccessModes | StorageClassName |
| --- | --- | --- | --- | --- | --- | --- | --- |
| alphacar-mongo-pv | PersistentVolume | driver.longhorn.io | 3 |  |  | ReadWriteOnce | longhorn |
| aichat-vector-store-pv | PersistentVolume |  |  |  |  | ReadWriteOnce |  |


## Job

_원본 시트: `Job` — 2행_

| NS | Name | Kind | Image | TTL | BackoffLimit | RestartPolicy | CPU Req | CPU Lim | Memory Req | Memory Lim | PVC | Mount Path |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| alphacar-be-ns | aichat-embedding-job | Job | 192.168.0.169/bh/alphacar-aichat:1.0.9 | 3600 | 3 | Never | 500m | 2000m | 1Gi | 2Gi | aichat-vector-store-pvc | /app/vector_store |


## CronJob

_원본 시트: `Cronjob` — 2행_

| NS | Name | Schedule | Image | Command | BackoffLimit | RestartPolicy |
| --- | --- | --- | --- | --- | --- | --- |
| alphacar-obsv-ns | monitoring-analysis-daily-report | 0 9 * * * | curlimages/curl:latest | POST /api/reports/generate | 1 | OnFailure |


## AI Chat 백엔드 상세

_원본 시트: `AICHAT` — 52행_

| 1. Kubernetes 리소스 정보 | col2 | col3 | col4 | col5 | col6 |
| --- | --- | --- | --- | --- | --- |
| 리소스 타입 | 이름 | 네임스페이스 | 이미지/설정 | 포트 | 리소스 (Requests/Limits) |
| Deployment | aichat-backend | alphacar-be-ns | 192.168.0.169/bh/alphacar-aichat:1.0.12 | 4000 | CPU: 300m/1000m, Memory: 512Mi/1Gi |
| Service | aichat-backend | alphacar-be-ns | ClusterIP | 4000 | - |
| PersistentVolume | aichat-vector-store-pv | alphacar-be-ns | hostPath: /data/aichat-vector-store | - | 10Gi |
| PersistentVolumeClaim | aichat-vector-store-pvc | alphacar-be-ns | ReadWriteOnce | - | 10Gi |
| Job | aichat-embedding-job | alphacar-be-ns | 192.168.0.169/bh/alphacar-aichat:1.0.12 | - | CPU: 500m/2000 |
| 2. 환경 변수 및 Secret |  |  |  |  |  |
| 환경 변수명 | 값/참조 | 타입 | 설명 |  |  |
| PORT | 4000 | 직접 설정 | 서비스 포트 |  |  |
| SERVICE_NAME | aichat-backend | 직접 설정 | 서비스 이름 |  |  |
| DATABASE_HOST | mongodb-0.mongodb-headless.alphacar.svc.cluster.local | ConfigMap (alphacar-env) | MongoDB 호스트 |  |  |
| DATABASE_PORT | 27017 | ConfigMap (alphacar-env) | MongoDB 포트 |  |  |
| DATABASE_USER | proj | Secret (mongodb-aichat-secret) | MongoDB 사용자 |  |  |
| DATABASE_PASSWORD | pass123 | Secret (mongodb-aichat-secret) | MongoDB 비밀번호 |  |  |
| DATABASE_NAME | triple_db | Secret (mongodb-aichat-secret) | 데이터베이스명 |  |  |
| AWS_REGION | us-east-1 | Secret (aws-bedrock-secret) | AWS 리전 |  |  |
| AWS_ACCESS_KEY_ID | AKIAVR45…(마스킹됨) | Secret (aws-bedrock-secret) | AWS 액세스 키 |  |  |
| AWS_SECRET_ACCESS_KEY | (암호화됨) | Secret (aws-bedrock-secret) | AWS 시크릿 키 |  |  |
| BEDROCK_EMBEDDING_MODEL_ID | amazon.titan-embed-text-v2:0 | Secret (aws-bedrock-secret) | 임베딩 모델 |  |  |
| BEDROCK_LLM_MODEL_ID | meta.llama3-3-70b-instruct-v1:0 | Secret (aws-bedrock-secret) | LLM 모델 |  |  |
| BEDROCK_GUARDRAIL_ID | nfdfeln14bg7 | Secret (aws-bedrock-secret) | Guardrail ID |  |  |
| BEDROCK_GUARDRAIL_VERSION | DRAFT | Secret (aws-bedrock-secret) | Guardrail 버전 |  |  |
| OTEL_EXPORTER_OTLP_ENDPOINT | http://alloy-agent:4317 | ConfigMap (alphacar-env) | OpenTelemetry 엔드포인트 |  |  |
| 3. API 엔드포인트 |  |  |  |  |  |
| 메서드 | 엔드포인트 | 경로 변환 | 설명 | 요청 형식 | 응답 형식 |
| POST | /api/chat/ask | /chat/ask | 텍스트 질의응답 | JSON: {message: "질문"} | JSON: {response: "답변", context_used: []} |
| POST | /api/chat/image | /chat/image | 이미지 업로드 및 분석 | multipart/form-data (file) | JSON: {response: "답변", identified_car: "차량명", context_used: []} |
| POST | /api/chat/knowledge | /chat/knowledge | 지식 추가 (관리용) | JSON: {content: "내용", source: "소스"} | JSON: {message: "Knowledge added.", source: "소스"} |
| 4. AWS Bedrock 모델 정보 |  |  |  |  |  |
| 용도 | 모델 ID | 파라미터 | 설명 |  |  |
| Embedding | amazon.titan-embed-text-v2:0 | - | 벡터 임베딩 생성 |  |  |
| LLM (텍스트) | us.meta.llama3-3-70b-instruct-v1:0 | maxTokens: 2048, temperature: 0.2 | 텍스트 생성 |  |  |
| Vision (이미지) | us.meta.llama3-2-90b-instruct-v1:0 | maxTokens: 500, temperature: 0.1 | 이미지 분석 및 차량 식별 |  |  |
| 5. 스토리지 정보 |  |  |  |  |  |
| 항목 | 값 | 설명 |  |  |  |
| PVC 이름 | aichat-vector-store-pvc | PersistentVolumeClaim 이름 |  |  |  |
| PV 이름 | aichat-vector-store-pv | PersistentVolume 이름 |  |  |  |
| 스토리지 크기 | 10Gi | 총 용량 |  |  |  |
| Access Mode | ReadWriteOnce | 단일 Pod 마운트만 가능 |  |  |  |
| 호스트 경로 | /data/aichat-vector-store | 실제 저장 경로 |  |  |  |
| 마운트 경로 | /app/vector_store | Pod 내부 마운트 경로 |  |  |  |
| 현재 사용량 | 약 10MB | docstore.json: 2.2MB, faiss.index: 7.4MB |  |  |  |
| 임베딩 차량 수 | 475대 | Vector Store에 저장된 차량 수 |  |  |  |
| 6.유지보수 |  |  |  |  |  |
| 항목 | 값 | 설명 |  |  |  |
| 배포 파일 경로 | k8s/backend/aichat-backend.yaml | Deployment 설정 |  |  |  |
| 임베딩 Job 파일 | k8s/backend/aichat-embedding-job.yaml | Job 설정 |  |  |  |
| ConfigMap 이름 | alphacar-env | 공통 환경 변수 |  |  |  |
| Secret 이름 | mongodb-aichat-secret, aws-bedrock-secret | 인증 정보 |  |  |  |
| Nginx 라우팅 | /api/chat/* → /chat/* | 경로 변환 규칙 |  |  |  |
| 응답 시간 | 텍스트: 2-5초, 이미지: 5-10초 | 성능 지표 |  |  |  |


## AI 리뷰 분석 스크립트

_원본 시트: `AI_RIVIEW_ANALAYZE` — 26행_

| 1. 코드 설명 | col2 | col3 |
| --- | --- | --- |
| 파일 | 경로 | 설명 |
| analyze-reviews.ts | dev/alphacar/backend/aichat/scripts/analyze-reviews.ts | 차량 리뷰 AI 분석 스크립트 |
| 2. 몽고디비 컬렉션 |  |  |
| 소스 컬렉션 | 타겟 컬렉션 | 데이터베이스 |
| danawa_vehicle_data | review_analysis | triple_db |
| 3.Data Processing Flow |  |  |
| 단계 | 작업 | 설명 |
| 1 | 데이터 로드 | danawa_vehicle_data에서 review 필드가 있는 차량 데이터 조회 |
| 2 | 그룹화 | vehicle_name 기준으로 차종별 그룹화 및 리뷰 통합 |
| 3 | 중복 제거 | review_id 또는 content 기준으로 중복 리뷰 제거 |
| 4 | 평점 계산 | overall_rating 및 rating_breakdown 평균 계산 |
| 5 | AI 분석 | AWS Bedrock을 통한 리뷰 텍스트 분석 |
| 6 | 결과 저장 | review_analysis 컬렉션에 Upsert 저장 |
| 4.AI Model Configuration |  |  |
| 항목 | 값 | 설명 |
| 모델 ID | us.meta.llama3-3-70b-instruct-v1:0 | AWS Bedrock Llama3 모델 |
| Max Tokens | 1024 | 최대 출력 토큰 수 |
| Temperature | 0.1 | 낮은 값으로 일관된 결과 생성 |
| 텍스트 제한 | 25000자 | 리뷰 텍스트 최대 길이 |
| 5. AI Analysis Prompt |  |  |
| 항목 | 내용 |  |
| 역할 | 전문 자동차 리뷰 분석가 |  |
| 입력 | 차량명과 리뷰 텍스트 (최대 25000자) |  |
| 출력 형식 | JSON only (설명 없이) |  |
| 출력 필드 | summary (3개), pros (3-5개), cons (3-5개), sentiment_ratio (positive/negative 합계 100) |  |


## AI 인프라 모니터링 대시보드

_원본 시트: `AI_INFRA` — 114행_

| 1. Dashboard Overview | col2 | col3 |
| --- | --- | --- |
| 항목 | 설명 | 값 |
| 접속 URL | 로컬 환경 | http://monitoring.192.168.0.160.nip.io |
| 접속 URL | 멀티마스터 환경 | http://monitoring.192.168.0.178.nip.io |
| 자동 새로고침 | K8s 클러스터 상태 | 30초 |
| 자동 새로고침 | 리소스 메트릭 | 5초 |
| 자동 새로고침 | 알림 및 해결책 | 30초 |
| #### Dashboard Sections |  |  |
| - 섹션 \| 설명 \| 데이터 소스 |  |  |
| - K8s 클러스터 상태 \| 건강 점수, AI 분석, 경고 목록 \| /api/k8s/status |  |  |
| - 리소스 메트릭 \| CPU, Memory, Pod 상태 \| Prometheus |  |  |
| - 알림 및 해결책 \| 문제 위치, 실행 가능한 명령어 \| checkResourceAlerts() |  |  |
| #### Dashboard Features |  |  |
| - 기능 \| 설명 \| 구현 방식 |  |  |
| - 건강 점수 표시 \| 0-100 점수, 색상 코딩 (빨강/노랑/초록) \| healthScore 계산 |  |  |
| - AI 분석 표시 \| 클러스터 상태 기반 AI 분석 결과 \| AWS Bedrock |  |  |
| - 경고 목록 \| Critical/Warning 경고 상세 정보 \| Prometheus 쿼리 |  |  |
| - 문제 위치 표시 \| namespace/pod-name 형식 \| 메트릭에서 추출 |  |  |
| - 해결책 표시 \| 실행 가능한 kubectl 명령어 포함 \| 자동 생성 |  |  |
| - 실시간 업데이트 \| 자동 새로고침으로 최신 상태 유지 \| setInterval |  |  |
| #### API Endpoints |  |  |
| - Method \| Endpoint \| Description \| Request \| Response |  |  |
| - GET \| /api/k8s/status \| K8s 클러스터 상태 조회 \| - \| JSON: {healthScore, status, criticalCount, warningCount, alerts, aiAnalysis, timestamp} |  |  |
| - POST \| /api/analyze/metrics \| 메트릭 분석 요청 \| JSON: {query: "prometheus_query"} \| JSON: {analysis, graphData, summary, alerts} |  |  |
| - POST \| /api/analyze/logs \| 로그 분석 요청 \| JSON: {level: "error", hours: 1} \| JSON: {analysis, logCount, hours} |  |  |
| - POST \| /api/analyze/traces \| 트레이스 분석 요청 \| JSON: {service: "service-name"} \| JSON: {analysis, traceData} |  |  |
| #### Health Score Calculation |  |  |
| - 항목 \| 점수 감소 \| 설명 |  |  |
| - Critical 경고 \| -20점/개 \| 심각한 문제 (Pod CrashLoopBackOff, Node NotReady, OOM Kills) |  |  |
| - Warning 경고 \| -5점/개 \| 주의 필요 (Pod Pending, High CPU/Memory Usage) |  |  |
| - 최소 점수 \| 0점 \| 점수는 0 이하로 내려가지 않음 |  |  |
| - 최대 점수 \| 100점 \| 문제 없을 때 |  |  |
| #### Health Score Status |  |  |
| - 점수 범위 \| 상태 \| 색상 \| 설명 |  |  |
| - 80-100 \| healthy \| 초록색 \| 정상 상태 |  |  |
| - 50-79 \| warning \| 노란색 \| 주의 필요 |  |  |
| - 0-49 \| critical \| 빨간색 \| 위급 상태 |  |  |
| #### Slack Notification Types |  |  |
| - 타입 \| 설명 \| 트리거 조건 |  |  |
| - 실시간 알림 \| 문제 발생 시 즉시 전송 \| checkResourceAlerts() 감지 시 |  |  |
| - 일일 리포트 \| 매일 오전 9시 전송 \| CronJob (0 9 * * *) |  |  |
| #### Real-time Alert Notification |  |  |
| - 항목 \| 설명 \| 값 |  |  |
| - 전송 시점 \| 문제 감지 즉시 \| 자동 |  |  |
| - 대상 \| Critical 경고 우선, Warning 경고 \| severity 기준 |  |  |
| - 형식 \| Slack Block Kit \| 구조화된 메시지 |  |  |
| #### Alert Message Structure |  |  |
| - 필드 \| 설명 \| 예시 |  |  |
| - 제목 \| 경고 심각도 및 메트릭명 \| 🚨 Pod CrashLoopBackOff |  |  |
| - 문제 위치 \| namespace/pod-name \| alphacar/monitoring-backend-xxx |  |  |
| - AI 분석 \| 문제 원인 분석 \| Pod가 계속 재시작되고 있습니다... |  |  |
| - 해결책 \| 실행 가능한 명령어 포함 \| kubectl logs -n alphacar pod-name --previous |  |  |
| #### Daily Report Notification |  |  |
| - 항목 \| 설명 \| 값 |  |  |
| - 전송 시간 \| 매일 오전 9시 \| CronJob 스케줄 |  |  |
| - 형식 \| 텍스트 리포트 \| Slack Block Kit |  |  |
| - 내용 \| 클러스터 건강 점수, 주요 이벤트, AI 한 줄 평 \| AI 생성 |  |  |
| #### Daily Report Structure |  |  |
| - 섹션 \| 설명 \| 내용 |  |  |
| - Executive Summary \| 요약 정보 \| 건강 점수, 주요 이벤트, AI 한 줄 평 |  |  |
| - Resource Efficiency \| 리소스 효율성 \| 과소/과다 프로비저닝 서비스, 비용 최적화 제안 |  |  |
| - Stability & Error Insights \| 안정성 및 오류 \| 오류 클러스터링, 자주 재시작하는 Pod |  |  |
| - Networking & Latency \| 네트워크 및 지연 \| P99 지연 트렌드, 5xx 오류율 |  |  |
| - AI Action Items \| 액션 아이템 \| 우선순위별 조치사항, 자동화 제안 |  |  |
| #### Slack Configuration |  |  |
| - 항목 \| 설명 \| Secret Key |  |  |
| - 알림 웹훅 URL \| 실시간 알림용 \| slack-webhook-url |  |  |
| - 리포트 웹훅 URL \| 일일 리포트용 \| slack-report-webhook-url |  |  |
| - Bot Token \| 고급 기능용 \| slack-bot-token |  |  |
| - 채널 ID \| 리포트 전송 채널 \| slack-channel-id |  |  |
| #### AI Analysis in Slack |  |  |
| - 기능 \| 설명 \| 모델 |  |  |
| - 문제 진단 \| 클러스터 상태 기반 문제 분석 \| AWS Bedrock (us.meta.llama3-3-70b-instruct-v1:0) |  |  |
| - 해결책 생성 \| 문제별 실행 가능한 kubectl 명령어 \| 자동 생성 |  |  |
| - 위치 정보 \| 정확한 문제 위치 (namespace/pod-name) \| Prometheus 메트릭 |  |  |
| - 감정 분석 \| 긍정/부정 비율 계산 \| AI 분석 |  |  |
| #### Alert Types in Slack |  |  |
| - Alert Type \| 심각도 \| Slack 메시지 형식 |  |  |
| - Pod CrashLoopBackOff \| Critical \| 🚨 이모지, 빨간색 강조 |  |  |
| - Excessive Pod Restarts \| Critical \| 🚨 이모지, 빨간색 강조 |  |  |
| - Node NotReady \| Critical \| 🚨 이모지, 빨간색 강조 |  |  |
| - Pod Pending \| Warning \| ⚠️ 이모지, 노란색 강조 |  |  |
| - Container OOM Kills \| Critical \| 🚨 이모지, 빨간색 강조 |  |  |
| - High Pod CPU Usage \| Warning \| ⚠️ 이모지, 노란색 강조 |  |  |
| - Critical Pod Memory Usage \| Warning \| ⚠️ 이모지, 노란색 강조 |  |  |
| - Node Disk Usage \| Warning \| ⚠️ 이모지, 노란색 강조 |  |  |
| #### Solution Commands in Slack |  |  |
| - 해결책 \| 명령어 예시 \| 설명 |  |  |
| - Pod 로그 확인 \| kubectl logs -n namespace pod-name --previous \| 이전 컨테이너 로그 확인 |  |  |
| - Pod 이벤트 확인 \| kubectl describe pod -n namespace pod-name \| Pod 상세 정보 및 이벤트 |  |  |
| - Pod 재시작 \| kubectl delete pod -n namespace pod-name \| 실패한 Pod 재시작 |  |  |
| - 리소스 제한 확인 \| kubectl describe pod -n namespace pod-name \| CPU/메모리 제한 확인 |  |  |
| - 노드 상태 확인 \| kubectl get nodes node-name -o wide \| 노드 상태 및 리소스 |  |  |
| - 노드 이벤트 확인 \| kubectl describe node node-name \| 노드 상세 정보 및 이벤트 |  |  |
| #### Slack Message Format |  |  |
| - 필드 \| 형식 \| 설명 |  |  |
| - 제목 \| Slack Block Kit Header \| 경고 심각도 및 메트릭명 |  |  |
| - 문제 위치 \| Section Block \| 📍 문제 위치: namespace/pod-name |  |  |
| - AI 분석 \| Section Block \| 📊 AI 분석: 분석 내용 |  |  |
| - 해결책 \| Section Block \| 💡 해결책: 각 해결책별 명령어 포함 |  |  |
| - 명령어 \| Code Block \|ctl command``` 형식 |  |  |
| #### AWS Bedrock Integration |  |  |
| - 항목 \| 값 \| 설명 |  |  |
| - 모델 ID \| us.meta.llama3-3-70b-instruct-v1:0 \| LLM 모델 |  |  |
| - Guardrail ID \| (Secret에서 로드) \| 콘텐츠 필터링 |  |  |
| - Guardrail Version \| DRAFT \| Guardrail 버전 |  |  |
| - Max Tokens \| 4000 \| 최대 출력 토큰 |  |  |
| - Temperature \| 0.1-0.2 \| 낮은 값으로 일관된 결과 |  |  |
| #### AI Prompt Structure |  |  |
| - 단계 \| 내용 \| 설명 |  |  |
| - 1 \| 클러스터 상태 정보 \| 건강 점수, Critical/Warning 경고 수 |  |  |
| - 2 \| 발견된 문제 목록 \| 각 경고의 메트릭, 값, 위치 |  |  |
| - 3 \| 분석 요청 \| 클러스터 상태 요약, 주요 문제점, 권장 조치사항 |  |  |
| - 4 \| 출력 형식 \| 구조화된 한국어 분석 결과 |  |  |
