# Probes (liveness · readiness · startup)

## 🟡 무엇인가
- **한 줄 정의**: Probe는 kubelet이 컨테이너 상태를 주기적으로 점검해 "재시작할지, 트래픽을 보낼지, 아직 시작 중인지"를 판단하는 진단 장치다.
- **핵심 개념**:
  - **Liveness = 재시작 판단**: `failureThreshold`만큼 연속 실패하면 kubelet이 컨테이너를 재시작. 데드락·행처럼 스스로 못 빠져나오는 상태 복구용.
  - **Readiness = 트래픽 판단**: 실패해도 재시작하지 **않고**, Pod를 Service Endpoints에서 제거해 트래픽만 끊는다. 준비되면 자동 복귀. 무중단 배포에 필수.
  - **Startup = 시작 보호**: startup이 성공하기 전까지 liveness·readiness는 실행되지 않는다. 허용 시작 시간 = `failureThreshold × periodSeconds`. 느린 앱을 조기 킬에서 보호하면서 liveness는 민감하게 유지.
  - **4가지 검사 방식**: `httpGet`(2xx·3xx 성공), `tcpSocket`, `exec`(종료코드 0), `grpc`.
  - **주요 파라미터 기본값**: `initialDelaySeconds` 0, `periodSeconds` 10, `timeoutSeconds` 1, `failureThreshold` 3 (successThreshold는 liveness/startup에서 1 고정).
  - **상태 연결**: readiness 통과 → Pod `Ready` 컨디션 True → 그때만 Service 로드밸런싱 대상.
- **공식문서**:
  - [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/) — 4가지 검사 방식, 파라미터 기본값, startup의 시작 보호 공식.
  - [Pod Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) — 프로브 결과가 `Ready` 컨디션·재시작에 반영되는 방식, startup 성공 전 다른 프로브 비활성화.
- **면접 포인트**:
  - **Q. liveness vs readiness 결정적 차이?** → 결과 행동. liveness 실패 = 컨테이너 **재시작**, readiness 실패 = **트래픽만 차단**(재시작 없음).
  - **Q. startup 프로브를 왜 따로 두나? liveness initialDelay를 키우면 안 되나?** → initialDelay를 키우면 그만큼 런타임 데드락 감지도 늦어진다(관측 공백). startup은 시작 동안만 liveness를 미룬다.
  - **자주 틀림**: httpGet은 200만이 아니라 **2xx·3xx면 성공**. 프로브 요청엔 앱 인증 헤더가 안 붙으므로 헬스 엔드포인트는 인증 없이 열어야 한다.

## 🟡 왜 우리 서비스에서?
- Compose `healthcheck` → K8s 세 프로브로 역할 분리. 워커 5대(각 8Gi/2CPU)로 자원이 빠듯해 재시작 폭풍·미준비 Pod 트래픽 유입이 곧 사용자 영향이라, `dang-be-ns`·`dang-fe-ns`·`dang-ai-ns` 앱 Deployment에 세 프로브 배치가 기본 원칙.
- **startup 1순위 = `dang-ai-ns`**: 모델 로딩 수십 초 동안 liveness 오진으로 재시작 루프에 빠지는 것을 `failureThreshold × periodSeconds` 시작 창으로 방지.
- **readiness는 3계층 NetworkPolicy(fe→be→db)와 짝**: 백엔드가 DB 커넥션 풀을 못 채우면 재시작 대신 readiness 실패로 트래픽만 끊고 회복 시 자동 복귀. 프론트 롤아웃 중 502 방지.
- **임계값은 관측 데이터로 튜닝**: `dang-obsv-ns`의 `kube_pod_container_status_restarts_total`·Ready 비율로 과민/과대 설정을 검증 — "수동 워크스루 검증" 방식과 일치.
- **리스크 — liveness 과민 설정**: 헬스 엔드포인트가 DB 등 외부 의존성까지 보면 DB 지연 시 멀쩡한 Pod 연쇄 재시작. 원칙은 "liveness는 자기 생존만, 외부 의존성은 readiness로".
