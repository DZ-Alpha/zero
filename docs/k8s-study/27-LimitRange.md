# LimitRange

## 🟡 무엇인가

- **한 줄 정의**: 하나의 네임스페이스 안에서 개별 컨테이너·Pod·PVC가 가질 수 있는 CPU·메모리·스토리지의 기본값·최솟값·최댓값을 강제하는 정책 오브젝트다.
- **핵심 개념**:
  - **개별 객체 단위 제약**: 컨테이너/Pod/PVC 한 개에 대한 규칙. 네임스페이스 전체 합계는 ResourceQuota의 일이며 둘은 별개다.
  - **주요 필드**: `defaultRequest`(requests 누락 시 주입), `default`(limits 누락 시 주입), `min`/`max`(허용 범위), `maxLimitRequestRatio`(limit/request 비율 상한).
  - **admission 시점에만 적용**: 검증·기본값 주입은 파드 생성/수정 시에만 일어난다. 이미 실행 중인 파드는 LimitRange를 바꿔도 영향받지 않는다.
  - **위반 시 403 거부**: min/max를 벗어난 Pod/PVC는 API 서버가 `403 Forbidden`으로 거부한다.
  - **기본값 정합성은 미검사**: `default`(limit)만 있고 파드가 그보다 큰 request를 적으면 request > limit 모순으로 생성 실패한다.
  - **PVC 스토리지에도 적용**: 컴퓨트 자원 외에 PVC 스토리지 요청의 min/max도 강제 가능.
- **공식문서**:
  - [LimitRange 개념 문서](https://kubernetes.io/docs/concepts/policy/limit-range/) — admission 단계에서만 검증, 기존 파드 유지, 위반 시 403 거부.
  - [Resource Quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/) — 네임스페이스 총량 제한은 ResourceQuota의 역할이라는 경계.
- **면접 포인트**:
  - **Q: LimitRange vs ResourceQuota?** → LimitRange는 개별 객체 한 개의 상·하한과 기본값("한 파드 최대 2Gi"), ResourceQuota는 네임스페이스 전체 합계("requests 합 최대 16Gi"). 보통 둘을 함께 쓰고, Quota가 requests 없는 파드를 거부하는 문제를 LimitRange의 기본값 주입이 보완한다.
  - **Q: LimitRange를 바꾸면 기존 파드도 재조정되나?** → 아니다. admission 시점에만 적용되며, 기존 파드는 재생성될 때 새 규칙을 받는다.
  - **Q: LimitRange가 노드 용량을 보고 막아주나?** → 아니다. 노드 실제 용량·가용량은 검사하지 않고 "숫자가 규칙 범위 안인가"만 본다. 배치는 스케줄러, 총량은 ResourceQuota의 몫.

## 🟡 왜 우리 서비스에서?

- 당당은 워커 5대(각 8Gi/2CPU)로 용량이 빠듯해, "limits 없는 컨테이너가 노드 메모리 독점 → 다른 서비스 OOM" 사고를 각 앱 네임스페이스(dang-be-ns / dang-fe-ns / dang-ai-ns) 입구에서 원천 차단하는 1차 방어선.
- requests/limits는 "도커 실측 관측 + 노드 용량 상한"으로 정하기로 했고, LimitRange `max`가 그 상한을 admission에서 강제한다(예: dang-ai-ns 추론 컨테이너가 limit 8Gi로 워커 한 대를 먹는 실수 차단).
- `defaultRequest` 자동 주입으로 requests 누락 시에도 스케줄러가 파드 크기를 올바로 인식해 워커 5대에 고르게 배치하고, ResourceQuota의 "requests 없는 파드 거부" 문제도 메운다.
- dang-obsv-ns의 Prometheus·Loki·Tempo 등은 PVC 스토리지 min/max로 "실수로 500Gi PVC 요청"을 방지. 단 dang-db-ns·dang-obsv-ns는 저장·상태 특성상 상한을 여유 있게 잡는다.
- 요약: ResourceQuota(총량)와 짝을 이뤄 "개발자 실수 → 노드 자원 독점" 단일 실패 지점을 봉인하는 자원 거버넌스 기본기.
