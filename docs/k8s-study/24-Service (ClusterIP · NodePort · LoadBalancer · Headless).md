# Service (ClusterIP · NodePort · LoadBalancer · Headless)

## 🟡 무엇인가
- **한 줄 정의**: 수시로 바뀌는 파드 집합 앞에 고정된 가상 IP와 DNS 이름을 세워, 클라이언트가 개별 파드 IP를 몰라도 안정적으로 접속하게 하는 추상화다.
- **핵심 개념**:
  - **ClusterIP (기본)**: 클러스터 내부 전용 가상 IP. 내부 마이크로서비스 통신의 기본형.
  - **NodePort**: 모든 노드의 동일 포트(기본 30000–32767)를 열어 `NodeIP:NodePort`로 외부 접근. 내부적으로 ClusterIP 위에 쌓인다.
  - **LoadBalancer**: 외부 로드밸런서로 고정 외부 IP 노출. NodePort/ClusterIP를 포함하는 상위 타입. 베어메탈은 MetalLB 같은 구현체 필요.
  - **Headless (`clusterIP: None`)**: 별도 타입이 아니라 설정(공식 4타입은 ClusterIP/NodePort/LoadBalancer/ExternalName). VIP·로드밸런싱 없음, kube-proxy 미관여. DNS가 파드 IP들을 직접 반환(A 레코드 다수). StatefulSet·파드 개별 지목에 사용.
  - **셀렉터와 EndpointSlice**: 라벨 셀렉터로 파드를 고르고 ready 파드 IP가 EndpointSlice에 반영되며, kube-proxy가 실제 트래픽을 분산한다.
  - **DNS 안정성**: `<서비스명>.<네임스페이스>.svc.cluster.local` 이름은 파드가 바뀌어도 그대로다.
- **공식문서**:
  - [Service | Kubernetes](https://kubernetes.io/docs/concepts/services-networking/service/) — 4개 타입 정의, NodePort 범위, Headless는 VIP 없이 DNS로 파드 IP 반환.
  - [StatefulSets | Kubernetes](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/) — StatefulSet은 Headless Service(`serviceName`)가 필수이며 각 파드가 `$(파드명).$(서비스도메인)` 고정 DNS를 얻는다.
- **면접 포인트**:
  - **Q. ClusterIP vs Headless?** → ClusterIP는 대표 VIP 하나에 kube-proxy가 로드밸런싱, Headless는 VIP·로드밸런싱 없이 DNS가 파드 IP 전부를 반환. "하나의 대표 vs 명단 전체".
  - **Q. NodePort/LoadBalancer는 ClusterIP를 대체하나?** → 아니다. 상위 타입이 하위를 포함하는 겹겹 구조 — LoadBalancer도 내부에 ClusterIP를 그대로 가진다.
  - **Q. StatefulSet에 왜 Headless를 쓰나?** → 각 파드가 개별 고정 주소를 가져야 하기 때문. VIP로 묶어 로드밸런싱하면 "0번 복제본에게만 붙기" 같은 stateful 요구를 못 맞춘다.
  - **오해**: "Headless도 로드밸런싱한다" → 틀림. 분산은 DNS로 받은 목록을 클라이언트가 알아서 하는 것.

## 🟡 왜 우리 서비스에서?
- 타입 선택 = 노출 정책: 사용자 대면인 프론트엔드(dang-fe-ns)만 NodePort/LoadBalancer(MetalLB 전제)로 외부(192.168.0.56:3001) 노출, 백엔드·AI·DB(dang-be-ns·dang-ai-ns·dang-db-ns)는 ClusterIP 내부 전용.
- Service가 "어디까지 보이나", NetworkPolicy default-deny 3계층이 "누가 실제로 붙나"를 통제 — 노출 최소화의 짝.
- 관측(dang-obsv-ns): Prometheus는 pull 방식이라 Service 엔드포인트(뒤의 파드들)를 발견해 파드별로 스크레이프 — 대표 하나가 아니라 파드 전부가 타깃이라 Headless/엔드포인트 기반 발견이 맞는 지점.
- StatefulSet 성격 워크로드(MinIO, Vault PoC replica 1, WAL 저장 계열)는 Headless로 파드별 고정 DNS 확보. 특히 **Alertmanager=3 gossip HA**는 피어 목록을 Headless DNS로 얻는다.
- 이관 검증 시 `nslookup`과 Prometheus targets로 직접 확인 — AI가 구성한 인프라를 수동 워크스루로 점검하는 우리 원칙.
