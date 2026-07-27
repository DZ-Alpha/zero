# k8s requests/limits 실측 기준선 (2026-07-26)

## 측정 조건

| 항목 | 값 |
| --- | --- |
| 데이터 출처 | monitoring VM Prometheus (100.110.81.51:9090), cAdvisor |
| 측정 구간 | 최근 7일 (Prometheus retention 15일) |
| production VM | `job="cadvisor-production-vm"` (10.10.10.30:8090) — CPU/MEM 모두 7일 p95·max |
| DB VM | `job="cadvisor-db-vm"` (10.10.20.10:8080) — CPU는 7일 p95, **메모리는 조회 시점 순간값** |
| 메모리 지표 | `container_memory_working_set_bytes` (k8s OOMKill 판정 기준과 동일) |
| CPU 지표 | `rate(container_cpu_usage_seconds_total[5m])` |

> ⚠️ **중요 전제**: 측정 구간 동안 실사용자 트래픽이 사실상 0이었다. 백엔드 서비스 CPU p95가
> 전부 9.4~9.5m로 거의 동일한데, 이는 요청 처리량이 아니라 헬스체크/런타임 유휴 비용이다.
> **이 표의 값은 "바닥값"이며, 부하테스트 전까지는 requests 산정의 하한선으로만 써야 한다.**

---

## 1. production VM — frontend / backend (7일)

| 컨테이너 | CPU p95 | CPU max | MEM p95 | MEM max |
| --- | ---: | ---: | ---: | ---: |
| dangdang-frontend | 6.7m | 28.3m | 172.1 MiB | **353.4 MiB** |
| dangdang-frontend-admin | 3.7m | 10.0m | 45.0 MiB | 95.7 MiB |
| b-gateway | 0.9m | 31.7m | 15.0 MiB | 18.7 MiB |
| main-service | 9.5m | 10.9m | 98.4 MiB | 109.6 MiB |
| login-service | 9.5m | 11.1m | 110.3 MiB | **250.0 MiB** |
| admin-service | 9.4m | 9.9m | 74.2 MiB | 129.2 MiB |
| product-service | 9.8m | **161.7m** | 126.6 MiB | 206.5 MiB |
| recipe-service | 9.5m | **127.0m** | 102.1 MiB | 113.7 MiB |
| ingredients-service | 9.4m | **187.8m** | 104.0 MiB | 117.4 MiB |
| community-service | 9.4m | **159.2m** | 100.8 MiB | 194.1 MiB |
| diet-service | 11.2m | 18.8m | 134.5 MiB | 232.2 MiB |
| ai | 9.5m | 17.5m | 132.8 MiB | 237.5 MiB |
| alloy (참고) | 3.5m | 25.5m | 157.1 MiB | 163.3 MiB |
| cadvisor (참고) | 72.7m | 87.1m | 249.3 MiB | 287.8 MiB |

**읽는 법**
- CPU p95는 전부 10m 내외 → 유휴 비용. 의미 있는 신호는 **max**다.
- product / recipe / ingredients / community 4종만 max가 127~188m로 튄다 → 배치성 작업 또는
  크롤링/집계 경로로 추정. **이 4종은 다른 서비스와 CPU 프로파일이 다르다.**
- 메모리는 login-service 250MiB, frontend 353MiB가 최고점.

---

## 2. DB VM — 데이터 계층

| 컨테이너 | CPU p95 (7일) | MEM (순간값) |
| --- | ---: | ---: |
| zero-kafka | 94.2m | **1099.7 MiB (1.07 GiB)** |
| zero-mongodb | 44.5m | 510.2 MiB |
| zero-pg-vector | 7.9m | 134.5 MiB |
| zero-redis | 5.8m | **13.3 MiB** |
| zero-minio | 1.8m | 156.8 MiB |
| zero-kafka-ui | 0.9m | 335.8 MiB |
| dangdang-pipeline-api | 23.5m | 47.8 MiB |
| dangdang-pipeline-db | 5.9m | 38.3 MiB |
| dangdang-pipeline-worker-1/2/3 | 0.3m each | 35.5 / 45.2 / 35.6 MiB |
| zero-recipe-consumer | 0.5m | 52.9 MiB |
| zero-recipe-thumbnail | 0.4m | 151.2 MiB |
| zero-outbox-publisher | 0.9m | 24.9 MiB |
| dangdang-activity-mongodb-consumer | 0.7m | 22.3 MiB |

---

## 3. 시방서 현재값 vs 실측 — 괴리 분석

| 워크로드 | 시방서 requests | 실측 기준 | 배율 | 판정 |
| --- | --- | --- | ---: | --- |
| **redis** cpu | 500m | 5.8m | **86배** | 과다 |
| **redis** memory | 1Gi | 13.3 MiB | **77배** | 과다 |
| **postgresql** cpu | 500m | 7.9m | 63배 | 과다 |
| **postgresql** memory | 1Gi | 134.5 MiB | 7.6배 | 과다 |
| **mongo** cpu | 500m | 44.5m | 11배 | 과다 |
| **mongo** memory | 1Gi | 510.2 MiB | 2.0배 | 적정 |
| **kafka** cpu | 500m | 94.2m | 5.3배 | 다소 과다 |
| **kafka** memory | 1Gi | 1.07 GiB | **0.93배** | ⚠️ **부족** |
| **backend** cpu | 200m | max 10~188m | 1~20배 | 서비스별 편차 큼 |
| **backend** memory | 256Mi | max 110~250 MiB | 1.0~2.3배 | 적정 (login은 여유 없음) |
| **frontend** cpu | 100m | max 28.3m | 3.5배 | 적정 |
| **frontend** memory | 512Mi | max 353.4 MiB | 1.4배 | 적정 |

**핵심 결론 3가지**

1. **메모리는 대체로 잘 잡혀 있다.** frontend/backend는 실측과 1.0~1.4배로 합리적.
2. **CPU requests가 전반적으로 과다하고, 특히 DB 계층이 심하다.** redis/postgresql은 두 자릿수 배율.
3. **kafka 메모리 requests 1Gi는 실측(1.07GiB)보다 작다.** 유일하게 **모자란** 항목이다.
   현 상태로 배포하면 kafka Pod가 requests를 즉시 초과한 채로 뜬다.

---

## 4. requests/limits 초안 (부하테스트 전 임시값)

산정 규칙:
- `requests.cpu` = 실측 max를 커버하는 최소 단위 (100m 단위 올림), 최소 50m
- `requests.memory` = 실측 max × 1.2 이상
- `limits.cpu` = requests의 3~5배 (CFS 스로틀링 여유 — CPU limit은 좁히면 p95가 튄다)
- `limits.memory` = 실측 max × 2 (초과 시 OOMKill이므로 여유 필요)

### frontend

| 워크로드 | requests.cpu | requests.memory | limits.cpu | limits.memory |
| --- | --- | --- | --- | --- |
| dang-fe-main | 100m | 512Mi | 500m | 1Gi |
| dang-fe-admin | 50m | 128Mi | 300m | 256Mi |
| gateway | 50m | 64Mi | 300m | 128Mi |

### backend — CPU 프로파일로 2군 분리

| 군 | 서비스 | requests.cpu | requests.memory | limits.cpu | limits.memory |
| --- | --- | --- | --- | --- | --- |
| A군 (저부하) | main, login, admin, diet, ai | **100m** | 320Mi | 500m | 640Mi |
| B군 (peak 높음) | product, recipe, ingredients, community | **200m** | 256Mi | 600m | 512Mi |

> login-service는 실측 max 250MiB로 현 requests 256Mi에 거의 붙어 있어 320Mi로 올렸다.

### 데이터 계층

| 워크로드 | requests.cpu | requests.memory | limits.cpu | limits.memory |
| --- | --- | --- | --- | --- |
| redis | 50m | 128Mi | 200m | 256Mi |
| postgresql | 100m | 256Mi | 500m | 512Mi |
| mongo | 100m | 768Mi | 500m | 1536Mi |
| kafka | 200m | **1536Mi** | 1 | 2Gi |
| minio | 50m | 256Mi | 300m | 512Mi |

---

## 5. 클러스터 용량 대조 — 가장 큰 리스크

`@Node.csv` 기준 워커 노드:

| | 대수 | CPU | 메모리 |
| --- | ---: | ---: | ---: |
| dang-worker1~5 | 5 | **2 each = 10** | 8192MB each = **40GB** |
| dang-master1~3 | 3 | 4 each = 12 | 5120MB each (일반 워크로드 스케줄 불가 — taint) |
| dang-proxy | 1 | 2 | 2048MB |

**일반 워크로드가 쓸 수 있는 건 워커 5대 = CPU 10 / 메모리 40GB 뿐이다.**
(kubelet/system reserved 제외하면 실질 allocatable은 CPU ~9, 메모리 ~35GB)

| 시나리오 | requests.cpu 합 | 워커 가용 10 대비 |
| --- | ---: | --- |
| 시방서 원본 ResourceQuota 합 | 28 CPU | **280%** ❌ |
| 단위 교정 후 실제 필요량 (HPA min) | 13.35 CPU | **134%** ❌ |
| 단위 교정 후 실제 필요량 (HPA max) | 17.95 CPU | **180%** ❌ |
| 위 4장 초안 적용 + HPA max 유지 | 약 11.5 CPU | 115% ❌ |
| 위 4장 초안 적용 + **HPA max 6→3** | 약 8.3 CPU | **83%** ✅ |

**requests는 오버커밋이 불가능하다.** 스케줄러는 노드 allocatable을 넘겨 Pod를 배치하지 않으므로,
초과분은 전부 `Pending`으로 쌓인다. 즉 **현재 시방서대로는 초기 배포조차 완료되지 않는다.**

### 해결 선택지

| 안 | 내용 | 비용 | 비고 |
| --- | --- | --- | --- |
| **A** | 워커 CPU 증설 (2→4) | Proxmox에서 vCPU 조정 | 마스터가 4 CPU인데 워커가 2 CPU인 현 배치가 역전이다. 마스터 3대를 2 CPU로 낮추고 워커를 4로 올리면 총량 변화 없이 해결 가능 |
| **B** | HPA max 6→3 | 설정 변경만 | 스케일아웃 여력 축소 |
| **C** | 4장 초안 적용 (requests 하향) | 시방서 수정 | 단독으로는 부족, B 또는 A와 병행 필요 |

**권장: A + C.** A는 자원 총량을 늘리지 않고 재배치만으로 해결되므로 비용이 사실상 0이다.

---

## 6. 다음 단계

1. 이 문서의 4장 초안을 시방서 Deployments에 반영할지 결정
2. 클러스터 용량 문제(5장) 해결안 A/B/C 중 선택 — **k8s 구축 착수 전 결정 필요**
3. k8s 이관 후 k6 부하테스트 → knee point에서 재측정 → limits/HPA target 확정
4. 재측정 시 이 문서를 갱신 (파일명의 날짜를 바꿔 이력 보존)
