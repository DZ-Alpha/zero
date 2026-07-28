# producer 이미지 — 발견+추출+게이트 → recipe.parsed 발행
# build context는 kafka/ 폴더 (자립형이라 data_pipeline 불필요, 가벼움)
FROM python:3.12-slim

WORKDIR /app

# 패키지 먼저 설치(레이어 캐시)
COPY requirements-producer.txt /app/
RUN pip install --no-cache-dir -r requirements-producer.txt

# kafka 패키지 전체를 /app/kafka 로 복사 → PYTHONPATH=/app 이면 import kafka.xxx 가능
COPY . /app/kafka
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# non-root 유저로 실행(보안). AWS 자격증명은 이 유저 홈(/home/app/.aws)에 마운트해야 함
# → compose 볼륨: ${HOME}/.aws:/home/app/.aws:ro
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

# 주기 실행 배치(1회 돌고 종료). cron/systemd가 `docker compose run --rm producer`로 호출.
CMD ["python", "-m", "kafka.producer.parse_producer"]
