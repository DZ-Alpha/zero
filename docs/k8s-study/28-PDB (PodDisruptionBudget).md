# PDB (PodDisruptionBudget)

## 🟡 무엇인가

- **한 줄 정의**: 노드 드레인 같은 "자발적 중단" 상황에서 한 애플리케이션의 파드가 동시에 몇 개까지 내려갈 수 있는지(또는 최소 몇 개는 살아있어야 하는지)를 보장하는 오브젝트다.
- **핵심 개념**:
  - **자발적 중단만 보호**: 노드 드레인·클러스터 축소·오토스케일러 회수 등만 조율한다. 하드웨어 고장·커널 패닉 같은 비자발적 중단은 막지 못한다(단, 손실은 예산에서 차감).
  - **두 가지 지정 방식**: `minAvailable` 또는 `maxUnavailable`(동시 지정 불가). 절대 수 또는 백분율(올림) 지정.
  - **Eviction API에만 작동**: `kubectl drain` 등 축출 API 경유만 통제. `kubectl delete pod`나 Deployment 삭제는 PDB를 우회한다.
  - **셀렉터는 컨트롤러와 일치**: 대상 Deployment/StatefulSet의 label selector와 동일해야 한다.
  - **너무 빡빡하면 drain 블록**: 축출 여유가 0이면(minAvailable = 복제본 수) node drain이 무한 대기한다. 최소 1개의 축출 여유가 필요.
  - **unhealthyPodEvictionPolicy**: 기본은 Healthy 대기. 오작동 앱도 드레인되게 하려면 `AlwaysAllow` 권장.
- **공식문서**:
  - [Disruptions 개념 문서](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/) — 자발적 중단만 제한, 비자발적 중단은 예산 차감만, 직접 삭제는 우회.
  - [Safely Drain a Node](https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/) — drain은 Eviction API로 축출하며 PDB 위반 요청은 재시도·대기.
- **면접 포인트**:
  - **Q: PDB가 하드웨어 장애 손실을 막아주나?** → 아니다. 축출 기반의 자발적 중단만 조율한다. HA에는 복제본 수·안티어피니티·다중 노드 분산이 함께 필요하다.
  - **Q: `kubectl delete pod`는 PDB를 지키나?** → 아니다. Eviction API 경유 축출에만 작동하므로 직접 삭제는 우회한다.
  - **Q: `minAvailable: 3`인데 복제본이 3개면?** → 축출 여유 0으로 drain이 영원히 블록된다. minAvailable은 복제본보다 작게 잡아야 유지보수가 가능하다. 복제본 1개면 PDB로도 무중단은 불가능하다.

## 🟡 왜 우리 서비스에서?

- dang-obsv-ns의 **Alertmanager 3개**(gossip 클러스터링, 물리 2호스트에서도 HA 유효 — Raft 정족수로 replica 1 PoC인 Vault와 대조)가 드레인 한 번에 동시에 날아가면 알림 파이프라인이 침묵. PDB `minAvailable: 2`로 gossip 정족수와 알림 발송 유지.
- 물리 2호스트·워커 5대의 작은 클러스터라 복제본이 한 노드에 몰릴 확률이 높고, PDB가 축출을 순차화해 "새 파드가 Ready 될 때까지 기다리는" 안전한 롤링 드레인을 강제한다.
- replica 1 Vault(PoC)나 GitOps로 재구성하는 무상태 Grafana는 PDB로 무중단 불가 — 여기선 재기동·재프로비저닝 속도가 관건.
- 운영 원칙: minAvailable은 "정족수 유지에 필요한 수"까지만(축출 여유 1개 이상 확보), 유지보수는 반드시 `kubectl drain`(축출 경로)으로 하고 `kubectl delete pod`로 노드를 비우지 않는다.
