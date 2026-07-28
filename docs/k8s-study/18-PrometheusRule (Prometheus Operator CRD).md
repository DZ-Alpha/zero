# PrometheusRule (Prometheus Operator CRD)

## 🟡 무엇인가

- **한 줄 정의**: Prometheus의 **알림 규칙(alerting rule)** 과 **기록 규칙(recording rule)** 을 YAML 오브젝트로 선언하는 Prometheus Operator CRD — "언제 울릴지"와 "무거운 쿼리 미리 계산"을 코드로 정의한다.

- **핵심 개념**:
  - **하나의 PrometheusRule = 여러 RuleGroup**, 그룹 안에 recording(`record`+`expr`)과 alerting(`alert`+`expr`+…)을 섞을 수 있고, 그룹 단위 `interval`(평가 주기)을 갖는다.
  - **알림 규칙 필드**: `alert`, `expr`, `for`(지속 시간, `pending`→`firing` 승격 조건), `labels`(severity 등 라우팅용), `annotations`(사람용 설명). `for`는 순간 튐(flapping) 오탐 방지 장치.
  - **기록 규칙**: `record`+`expr` 결과를 **새 시계열로 저장**(알람 안 울림). 네이밍 관례 **`level:metric:operations`**(예: `pod:container_cpu_usage_seconds:rate5m`).
  - **역할 분리**: 규칙 **평가·발화는 Prometheus**, 발화된 알람의 **중복제거·그룹핑·라우팅·무음·발송은 Alertmanager**(push로 전달받음).
  - **선택은 Prometheus의 `ruleSelector`**(+ `ruleNamespaceSelector`)가 하고, 변경은 Operator가 **재시작 없이** 반영. 잘못된 PromQL은 **admission webhook**이 생성 시점에 차단.
  - `for`(Prometheus의 지속 조건)와 Alertmanager의 `group_wait`/`group_interval`(발송 타이밍)은 **다른 지연**이다.

- **공식문서**:
  - <https://prometheus-operator.dev/docs/getting-started/design/> — PrometheusRule CRD, `ruleSelector` 선택, 무재시작 반영, 어드미션 웹훅 검증.
  - <https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/> — 알림 규칙 필드 의미와 Prometheus→Alertmanager 전송 흐름.

- **면접 포인트**:
  - **Q. recording vs alerting rule?** → recording은 무거운/자주 쓰는 쿼리를 미리 계산해 새 시계열로 저장(성능 최적화), alerting은 조건이 참이면 알람 발화(Alertmanager로 전송).
  - **Q. 알람은 누가 울리고 누가 보내나?** → 평가·발화는 Prometheus, 발송·라우팅은 Alertmanager. **Alertmanager는 규칙을 평가하지 않는다** — 흔한 오해.
  - **Q. PrometheusRule 만들면 슬랙이 오나?** → 아니다. CRD는 **발화까지만** 책임. 전달엔 Alertmanager 라우팅/리시버 설정(+네트워크·시크릿)이 필요하다.

---

## 🟡 왜 우리 서비스에서?

- `dang-obsv-ns`에서 **수집은 ServiceMonitor, 판단은 PrometheusRule**. 알람을 UI 수기 대신 **CRD로 코드화해 Git(ArgoCD)** 에 두기로 결정 — 리뷰·버전 관리·롤백 대상이 된다.
- 발화는 **Alertmanager 3-replica**(gossip 기반이라 물리 2호스트에서도 HA 유효 — 우리 결정)로 모여 슬랙으로 발송.
- 알림 규칙 후보: `up == 0`, 컨테이너 메모리 limit 90% 초과, Prometheus/Loki/Tempo PVC(WAL) 사용률 임박, cert-manager TLS 만료 임박, **Vault sealed**(PoC replica 1이라 조기 경보 중요), Kyverno 거부 급증. `labels.severity`로 라우팅.
- 슬랙까지 울리려면 (1) Alertmanager 라우팅/리시버 (2) default-deny 위 슬랙 egress 허용 (3) webhook 시크릿(평문 금지 — Sealed Secrets/Vault) 세트가 필요 — 알람 미발송 시 파이프라인 전체를 볼 것.
- **현행 유의점**: 일부 알람은 Grafana Alerting(`provenance=api`)과 공존 중. 방향은 인프라·플랫폼 알람은 PrometheusRule(GitOps)로 표준화, 대시보드 밀착 알람만 Grafana에 잔류 — 중복 발화 방지 위해 소유권 구분이 과제.
