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

EXPOSE 8010

# Docker 데몬이 상시 헬스 체크 (CIS Docker Benchmark v1.8.0, 4.6/5.27).
# curl을 추가 설치하지 않고 표준 라이브러리만으로 확인 (불필요한 패키지 설치 지양, CIS 4.3).
# 각 서비스에 이미 /health 엔드포인트가 있음(재헌님 인계 메모 기준 전 서비스 공통 구현).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8010/health', timeout=2)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
