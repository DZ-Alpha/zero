# ResourceQuota

## 🟡 무엇인가
- **한 줄 정의**: ResourceQuota는 네임스페이스 전체가 쓸 수 있는 자원 총량(CPU·메모리·스토리지)과 오브젝트 개수의 상한을 정해, 한 네임스페이스의 자원 독식을 막는 오브젝트다.
- **핵심 개념**:
  - **컴퓨트 총량**: `requests.cpu`/`requests.memory`/`limits.cpu`/`limits.memory` — 네임스페이스 내 모든 비종료 파드의 합계를 제한. requests는 예약(스케줄링), limits는 상한(CPU throttle / 메모리 OOMKill).
  - **스토리지·오브젝트 개수**: `requests.storage`, `persistentvolumeclaims`, `pods`, `services` 등과 일반형 `count/<resource>.<group>` — 오브젝트 폭주 자체를 입구에서 차단.
  - **admission 문지기**: 생성/증설 시점에 API 서버가 검사, 한도 초과면 `403 Forbidden`. 이미 떠 있는 리소스에는 소급 적용 안 됨.
  - **강제성**: CPU/메모리 Quota가 걸리면 그 네임스페이스의 모든 새 파드는 requests/limits를 반드시 명시해야 한다 — 짝꿍 LimitRange로 기본값을 자동 주입하는 게 표준 패턴.
  - **스코프**: `scopeSelector`(BestEffort, Terminating, PriorityClass 등)로 적용 대상 파드를 좁힐 수 있다.
- **공식문서**:
  - [Resource Quotas | Kubernetes](https://kubernetes.io/docs/concepts/policy/resource-quotas/) — 네임스페이스당 총량·개수 제한, cpu/memory Quota 시 requests/limits 필수, 초과 시 403.
  - [Limit Ranges | Kubernetes](https://kubernetes.io/docs/concepts/policy/limit-range/) — 컨테이너/파드/PVC의 기본값·최소·최대를 정해 Quota가 요구하는 값을 자동으로 채움.
- **면접 포인트**:
  - **Q. ResourceQuota vs LimitRange?** → Quota는 네임스페이스 전체 합계의 상한, LimitRange는 개별 컨테이너/파드/PVC의 기본값·최소·최대. Quota만 걸면 값 안 적은 파드가 계속 거절되므로 둘은 짝으로 쓴다.
  - **Q. Quota를 낮추면 기존 파드가 죽나?** → 아니다. 소급 적용되지 않고 새 생성/증설 요청부터 적용된다.
  - **Q. 네임스페이스만 나누면 자원이 격리되나?** → 아니다. 네임스페이스는 Quota를 걸 자리를 줄 뿐, ResourceQuota 오브젝트를 실제로 만들어야 상한이 생긴다.

## 🟡 왜 우리 서비스에서?
- 물리 2호스트, worker 8Gi/2CPU의 좁은 자원을 `dang-fe-ns`·`dang-be-ns`·`dang-ai-ns`·`dang-db-ns`·`dang-obsv-ns`·보안 네임스페이스들이 나눠 쓰므로, 네임스페이스별 Quota가 필수. 값은 도커 실측 관측치 + 노드 용량 상한 기준.
- `dang-obsv-ns`가 특히 중요: Prometheus는 카디널리티 폭증에 취약해 메모리가 급증할 수 있는데, `limits.memory` 총량 Quota로 폭발 반경을 네임스페이스 안에 가둔다(사고 예방이 아니라 피해 격리 방화벽).
- `persistentvolumeclaims` 개수·`requests.storage` Quota로 로컬 PVC(WAL)+MinIO 구조에서 PVC 무한 증식을 차단, `pods` 상한으로 HPA/재시도 폭주도 억제.
- CPU/메모리 Quota를 거는 순간 모든 새 파드가 requests/limits 명시 필수 → 각 네임스페이스에 LimitRange를 함께 배포해 기본값 자동 주입.
- `dang-obsv-ns`·`dang-db-ns`는 저장·상태 특성을 감안해 넉넉히 잡되 상한은 유지. 현재 수치는 1차 상한이며 K8s 이관 후 부하테스트로 재조정 전제.
