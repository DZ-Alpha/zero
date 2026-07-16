# 멀티 스테이지 빌드(Docker 공식 권장 패턴, "Multi-stage builds"): 의존성 설치용 빌드 스테이지와
# 실행용 최종 스테이지를 분리해, pip 캐시/wheel 빌드 산출물 등이 최종 이미지에 남지 않게 한다.
# 가상환경(venv)에 설치한 뒤 그 디렉터리만 최종 스테이지로 복사하는 방식은 Docker 공식
# Python 샘플에서 쓰는 표준 패턴이다.
FROM python:3.12-slim@sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28 AS builder

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY ci_sandbox/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim@sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28

# non-root 사용자로 실행 (Docker 공식 권장: USER로 전환)
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY ci_sandbox/app ./app

# setuid/setgid 비트 제거 (CIS Docker Benchmark 4.8 - 방어 심층화)
RUN find / -xdev -perm /6000 -type f -exec chmod a-s {} \; 2>/dev/null || true

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 컨테이너가 살아있는 동안 Docker 데몬이 상시 헬스 체크 (CIS Docker Benchmark v1.8.0, 4.6/5.27).
# curl을 추가 설치하지 않고 표준 라이브러리만으로 확인 (불필요한 패키지 설치 지양, CIS 4.3).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
