# thumbnail 이미지 — recipe.parsed 소비 → 영상다운(yt-dlp)+프레임추출(ffmpeg)+Nova Pro 검증 → UPDATE
# 유일하게 ffmpeg(시스템)를 포함하므로 제일 무겁다. build context는 kafka/ 폴더.
FROM python:3.12-slim

# 프레임 추출용 ffmpeg (extract_lib가 subprocess로 호출)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-thumbnail.txt /app/
RUN pip install --no-cache-dir -r requirements-thumbnail.txt

COPY . /app/kafka
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# non-root 유저로 실행(보안). AWS 자격증명은 /home/app/.aws에 마운트.
# ⚠️ /data/thumbnails(호스트 마운트)에 이 유저가 쓸 수 있어야 함 — 서버에서
#    /opt/zero-infra/data/thumbnails 폴더 소유/권한을 uid 10001이 쓸 수 있게 하거나
#    (chmod 777 또는 chown 10001). 권한 문제 시 배포 README 참고.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

# 완성샷 저장 경로(compose에서 /data/thumbnails 볼륨 마운트)
# 상시 데몬: recipe.parsed를 별도 그룹으로 소비
CMD ["python", "-m", "kafka.thumbnail.thumbnail_worker"]
