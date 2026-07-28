# 멀티 스테이지 빌드(Docker 공식 권장 패턴) - 의존성 설치 산출물을 최종 이미지에서 제외한다.
# build-once: PR에서 1회 빌드/스캔 후 staging에 push, main 병합 시 재빌드 없이
# production repo로 digest 승격(.github/workflows/build-test.yml 참고).
FROM python:3.12-slim@sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28 AS builder

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# OTel 계측 파일럿(otel-guide.md) - 설치된 라이브러리(fastapi/httpx/redis/asyncpg 등)에
# 맞는 auto-instrumentation 패키지를 골라 넣는다. requirements.txt가 바뀌면
# 여기서 골라지는 패키지 조합도 바뀔 수 있어 빌드 시점에 매번 실행한다.
RUN opentelemetry-bootstrap -a install

FROM python:3.12-slim@sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28

# non-root 사용자로 실행 (Docker 공식 권장: USER로 전환)
# UID/GID를 숫자로 명시 — K8s PSA restricted의 runAsNonRoot는 이미지 USER가
# 숫자여야 non-root 검증 가능(이름 appuser만으론 CreateContainerConfigError).
RUN groupadd -r -g 10001 appuser && useradd -r -u 10001 -g appuser appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY app ./app

# setuid/setgid 비트 제거 (CIS Docker Benchmark 4.8 - 방어 심층화)
RUN find / -xdev -perm /6000 -type f -exec chmod a-s {} \; 2>/dev/null || true

RUN chown -R appuser:appuser /app
# 숫자 UID로 지정 — K8s가 non-root(≠0)임을 검증 가능하게(이름 아님)
USER 10001

EXPOSE 8000

# Docker 데몬이 상시 헬스 체크 (CIS Docker Benchmark v1.8.0, 4.6/5.27).
# curl을 추가 설치하지 않고 표준 라이브러리만으로 확인 (불필요한 패키지 설치 지양, CIS 4.3).
# 각 서비스에 이미 /health 엔드포인트가 있음(재헌님 인계 메모 기준 전 서비스 공통 구현).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

CMD ["opentelemetry-instrument", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
