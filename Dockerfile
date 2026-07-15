FROM python:3.12-slim@sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28

# non-root 사용자로 실행 (Docker 공식 권장: USER로 전환)
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY ci_sandbox/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ci_sandbox/app ./app

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
