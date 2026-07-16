# 백엔드 서비스 Dockerfile 하드닝 템플릿

| 작성일자 | 2026-07-16 |
|---|---|
| 작성자명 | 김지훈 |
| 대상 | `backend/*-service` 8개(admin/community/diet/ingredients/login/main/product/recipe) |
| 근거 | `docs/security/Docker_이미지_보안_정의서_20260715.md`와 동일 — Docker 공식 문서 + OWASP Docker Security Cheat Sheet + CIS Docker Benchmark v1.8.0 |
| 성격 | **적용 대기 템플릿** — `backend/` 브랜치(PR #19, 재헌님 소유)는 직접 수정하지 않고, 그대로 복사해 적용할 수 있는 템플릿만 준비함. 실제 적용은 재헌님이 각 서비스에 반영 |

## 왜 별도 문서로 두었나

8개 서비스의 Dockerfile을 직접 고쳐서 PR을 올릴 수도 있었지만, 이건 재헌님이 활발히 커밋 중인
브랜치(`Jheon/backend-login-service`)라 다른 사람이 임의로 손대면 충돌·혼선의 원인이 됩니다.
그래서 "그대로 복사해서 쓸 수 있는 완성된 템플릿"만 준비하고, 실제 반영은 재헌님이 하시도록
남겨둡니다.

## 지금 8개 서비스 Dockerfile의 실제 상태 (2026-07-16 확인)

8개 전부 아래와 완전히 동일한 템플릿입니다(포트 번호만 다름):

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`ci_sandbox`에 이미 적용된 보안 표준(`docs/security/Docker_이미지_보안_정의서_20260715.md`)이
하나도 반영되어 있지 않습니다 — base image digest pin, non-root 사용자, setuid/setgid 제거,
HEALTHCHECK, 멀티 스테이지 빌드 전부 없음.

## 하드닝된 템플릿 (그대로 복사해서 쓰면 됨)

포트 번호(`{{PORT}}`)만 서비스별로 바꾸면 됩니다.

```dockerfile
# 멀티 스테이지 빌드(Docker 공식 권장 패턴) - 의존성 설치 산출물을 최종 이미지에서 제외한다.
FROM python:3.12-slim@sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28 AS builder

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim@sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28

# non-root 사용자로 실행 (Docker 공식 권장: USER로 전환)
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY app ./app

# setuid/setgid 비트 제거 (CIS Docker Benchmark 4.8 - 방어 심층화)
RUN find / -xdev -perm /6000 -type f -exec chmod a-s {} \; 2>/dev/null || true

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE {{PORT}}

# Docker 데몬이 상시 헬스 체크 (CIS Docker Benchmark v1.8.0, 4.6/5.27).
# curl을 추가 설치하지 않고 표준 라이브러리만으로 확인 (불필요한 패키지 설치 지양, CIS 4.3).
# 각 서비스에 이미 /health 엔드포인트가 있음(재헌님 인계 메모 기준 전 서비스 공통 구현).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:{{PORT}}/health', timeout=2)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "{{PORT}}"]
```

## 서비스별 포트 매핑 (재헌님 인계 메모 기준)

| 서비스 | `{{PORT}}` |
|---|---|
| login-service | 8000 |
| admin-service | 8008 |
| main-service | 8010 |
| community-service | 8012 |
| recipe-service | 8014 |
| product-service | 8016 |
| ingredients-service | 8018 |
| diet-service | 8020 |

## 컨테이너 실행 시점 하드닝 (Dockerfile이 아니라 배포 설정에 적용)

`ci_sandbox`의 `infra/ci-sandbox/docker-compose.yml`에 적용된 아래 항목들은 백엔드 서비스가
실제 배포될 때(현재는 로컬 개발 단계, 배포 대상 미정) 그대로 적용 권장:

```yaml
cap_drop:
  - ALL
security_opt:
  - no-new-privileges:true
read_only: true
tmpfs:
  - /tmp
mem_limit: 256m   # 서비스별 실측 후 조정
cpus: 0.5         # 서비스별 실측 후 조정
pids_limit: 100
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

## CI 커버리지 (이미 반영 완료)

`build-test.yml`에 `backend-build-test`(의존성 설치+import 스모크 체크)와
`backend-image-scanning`(Trivy 취약점 스캔)이 이미 매트릭스로 추가되어 있습니다(2026-07-16,
PR #27). 이 Dockerfile 하드닝을 적용하면 `backend-image-scanning`의 Trivy 스캔 결과도
더 나아집니다(현재는 non-digest-pin 베이스 이미지라 스캔 시점마다 결과가 달라질 수 있음).
