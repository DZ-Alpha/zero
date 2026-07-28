# ServiceMonitor / PodMonitor (Prometheus Operator CRD)

## 🟡 무엇인가

- **한 줄 정의**: "이 라벨을 가진 Service(또는 Pod)를 이런 경로·주기로 긁어라(scrape)"를 YAML로 선언하는 Prometheus Operator CRD — `prometheus.yml`을 손대지 않고 대상 등록을 K8s 오브젝트로 관리한다.

- **핵심 개념**:
  - **선언은 CRD, 실제 설정은 Operator가 생성**: CRD는 "의도"만 담고, Operator가 Prometheus 스크레이프 설정으로 번역해 **재시작 없이** 동적 반영한다.
  - **누가 볼지는 Prometheus가 정한다**: Prometheus 오브젝트의 `serviceMonitorSelector`/`podMonitorSelector`(+ NamespaceSelector)가 라벨로 선택. **빈 셀렉터(`{}`)=전부 매치, null=매치 안 함**.
  - **ServiceMonitor**: Service를 라벨로 골라 그 뒤 파드를 긁는다. `endpoints[].port`는 **Service의 named port**(숫자 X) → 대상에 Service가 있어야 한다.
  - **PodMonitor**: Service 없이 **파드를 직접 라벨로** 긁는다. `podMetricsEndpoints[].port`는 파드의 named port. Job/DaemonSet/사이드카에 적합.
  - **라벨 매칭 3단**: Prometheus→ServiceMonitor→Service→파드. 세 단계 라벨 중 하나만 어긋나도 대상이 안 뜬다.
  - **크로스 네임스페이스**: CRD는 워크로드와 같은 ns에 두고, 다른 ns의 Prometheus가 `serviceMonitorNamespaceSelector`로 가로질러 발견(GitOps 패턴).

- **공식문서**:
  - <https://prometheus-operator.dev/docs/getting-started/design/> — 라벨 셀렉션으로 대상 발견, 셀렉터로 CRD 선택, 재시작 없는 동적 반영.
  - <https://prometheus-operator.dev/docs/api-reference/api/> — `endpoints`(Service named port) vs `podMetricsEndpoints`(파드 named port) API 스키마.

- **면접 포인트**:
  - **Q. ServiceMonitor vs PodMonitor?** → 전자는 Service를 골라 긁고(Service 필수, Service의 named port), 후자는 파드를 직접 긁는다(Service 불필요). 기본은 ServiceMonitor, Service 없는 워크로드엔 PodMonitor.
  - **Q. 만들었는데 안 긁힌다?** → 90% 라벨 문제: ① `serviceMonitorSelector` 불일치 ② NamespaceSelector가 대상 ns 미포함 ③ `selector`↔Service 라벨 불일치 ④ `port`에 숫자 기입(named여야 함).
  - **Q. ServiceMonitor가 스스로 긁나?** → 아니다. 긁는 주체는 **Prometheus**. CRD는 "대상 선언"일 뿐이다.

---

## 🟡 왜 우리 서비스에서?

- Prometheus(`dang-obsv-ns`)는 pull 방식 — 대상을 `prometheus.yml` 수기 대신 **CRD로 선언**하기로 결정. 각 대상 ns(`dang-be-ns`·`dang-fe-ns`·`dang-ai-ns`·`dang-db-ns`)에 ServiceMonitor를 함께 배포하고 `serviceMonitorNamespaceSelector`로 발견.
- **Service 있는 대상은 ServiceMonitor**: kube-state-metrics, Grafana, `/metrics` 노출 백엔드/AI 앱. **DaemonSet(node-exporter·otel-agent)은 PodMonitor 후보** — 파드 단위 관측이 자연스럽다(kube-prometheus-stack은 둘 다 가능, 스택 구성값에 맞춰 택일).
- node-exporter/otel-agent는 hostPath(/proc,/var/log)·hostNetwork 필요로 **privileged 전용 ns로 분리**(hostPath는 PSS baseline도 금지 — 01 문서 정정), 나머지 `dang-obsv-ns` 스택은 restricted 유지.
- **CRD·RBAC·NetworkPolicy는 한 세트**: 크로스 ns 스크레이프엔 최소권한 read ClusterRole + default-deny 위 scrape egress 허용이 있어야 실제로 긁힌다.
- 모든 CRD는 **GitOps(ArgoCD)** 관리 — "관측 대상 = 코드". 판단(언제 울리나)은 짝인 PrometheusRule 문서 참조.
