# HPA (HorizontalPodAutoscaler) + Metrics API

## 🟡 무엇인가
- **한 줄 정의**: HPA는 CPU 등 지표를 보고 Pod(replica) 수를 자동으로 늘리고 줄이는 컨트롤러이며, Metrics API는 그 판단에 쓸 사용률 숫자를 공급하는 표준 통로다.
- **핵심 개념**:
  - **수평 vs 수직**: HPA는 Pod **개수**, VPA는 Pod당 requests/limits **크기** 조절. HPA는 DaemonSet처럼 스케일 불가능한 오브젝트엔 적용 안 됨.
  - **파이프라인**: cAdvisor(kubelet 내장) → kubelet `/metrics/resource` → metrics-server(약 15초 주기 집계) → Metrics API(`metrics.k8s.io`) → HPA. metrics-server가 빠지면 HPA는 unknown으로 동작 불가.
  - **계산식**: `desiredReplicas = ceil[currentReplicas × (현재값/목표값)]`. 비율이 1.0±10%(기본 tolerance 0.1) 이내면 무동작으로 출렁임 방지.
  - **비대칭 안정화**: 스케일 업은 빠르게(stabilization window 기본 0초), 다운은 보수적으로(기본 300초). 다운 시 윈도우 내 최고 추천값 채택.
  - **requests 필수**: CPU 사용률(%) = 사용량 ÷ requests. requests 없으면 CPU% 기반 HPA 성립 불가.
- **공식문서**:
  - [Horizontal Pod Autoscaling](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/) — 공식 계산식, tolerance 0.1, 스케일 불가 오브젝트 제외.
  - [Resource metrics pipeline](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/) — cAdvisor→kubelet→metrics-server→Metrics API 파이프라인 구조.
- **면접 포인트**:
  - **Q. 왜 메모리 HPA는 스케일 다운이 잘 안 되나?** → JVM·Go 런타임·캐시는 부하가 빠져도 메모리를 반납하지 않아 사용률이 높게 유지된다. 1차 지표는 CPU, 메모리는 상한 방어용.
  - **Q. Prometheus가 있으면 metrics-server 불필요?** → 아니다. 기본 HPA는 Metrics API를 읽는데 이건 metrics-server만 채운다. Prometheus로 HPA 하려면 prometheus-adapter로 custom metrics API를 별도 연결.
  - **오해**: "HPA가 CPU를 밀리코어 절대값으로 본다" → 기본은 requests 대비 사용률(%)이다. HPA·VPA를 같은 지표(CPU)에 동시 적용하면 서로 싸우므로 금지.

## 🟡 왜 우리 서비스에서?
- HPA는 **상태 없는 앱 tier(dang-be-ns / dang-fe-ns / dang-ai-ns)에만 선별 적용**. 트래픽 따라 replica를 조절하는 게 자연스러운 계층.
- 임계값(targetCPUUtilization)은 지금 박지 않는다 — 부하테스트가 K8s 이관 후로 이월된 상태라, metrics-server를 먼저 세워 `kubectl top`으로 실측 후 확정.
- 지표는 **CPU 기준**: dang-ai-ns처럼 모델·캐시를 메모리에 상주시키는 워크로드는 메모리 HPA로 축소 불가. 메모리는 requests/limits로 OOM 방어만.
- **HPA 비대상 사례가 우리 스택에 그대로 있음**: OTel Collector Agent는 DaemonSet(노드당 1개), Alertmanager=3(gossip HA)·Vault=1(Raft 정족수)은 replica 고정 — HPA 걸면 오히려 깨진다.
- **Prometheus·kube-state-metrics·node-exporter는 HPA 데이터 소스가 아님**: 관측 경로일 뿐. HPA 전제 조건은 metrics-server 설치·검증(kube-system 등, dang-obsv-ns 밖)이며 `kubectl top pod` 확인 후 HPA 매니페스트를 얹는다.
