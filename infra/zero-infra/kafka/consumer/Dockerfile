# consumer 이미지 — recipe.parsed 소비 → 적재 + common영양 + substituted 매칭/영양/합산/base
# build context는 kafka/ 폴더 (자립형). 상시 데몬.
FROM python:3.12-slim

WORKDIR /app

COPY requirements-consumer.txt /app/
RUN pip install --no-cache-dir -r requirements-consumer.txt

COPY . /app/kafka
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# non-root 유저로 실행(보안). AWS 자격증명은 /home/app/.aws에 마운트
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

# 상시 실행: recipe.parsed를 계속 poll (compose에서 restart: unless-stopped)
CMD ["python", "-m", "kafka.consumer.recipe_consumer"]
