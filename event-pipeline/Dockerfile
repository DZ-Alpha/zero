FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY sql ./sql

RUN useradd --create-home --uid 10001 pipeline
USER pipeline

CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8080"]

