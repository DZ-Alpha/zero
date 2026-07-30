# -*- coding: utf-8 -*-
import json, os, shutil, time
from pathlib import Path

import boto3
from confluent_kafka import TopicPartition

from kafka.config import TOPIC_PARSED, GROUP_THUMBNAIL
from kafka.common import kafka_client, db
from kafka.thumbnail import extract_lib as ex   # 자립 복사 모듈

# 컨테이너 내부 경로. compose가 호스트 /opt/zero-infra/data/thumbnails 를 여기에 마운트한다.
THUMB_DIR = Path("/data/thumbnails")
# DB thumbnail_url에 저장하는 경로 형태(기존 98건과 통일: /data/thumbnails/{recipe_id}.jpg)
URL_PREFIX = "/data/thumbnails"
DB_WAIT_SECONDS = int(os.environ.get("THUMBNAIL_DB_WAIT_SECONDS", "300"))
DB_POLL_SECONDS = int(os.environ.get("THUMBNAIL_DB_POLL_SECONDS", "5"))
RETRY_BACKOFF_SECONDS = int(os.environ.get("THUMBNAIL_RETRY_BACKOFF_SECONDS", "10"))
_client = None


def _bedrock():
    global _client
    if _client is None:
        # Nova Pro는 us-east-1에만 있으므로 extract_lib의 BEDROCK_REGION(us-east-1)을 쓴다.
        # AWS_DEFAULT_REGION(ap-northeast-2)을 쓰면 Nova Pro 호출이 실패한다.
        _client = boto3.client("bedrock-runtime", region_name=ex.BEDROCK_REGION)
    return _client


def extract_frame_once(client, video_id: str, recipe_name: str) -> "Path | None":
    """다운로드→타임스탬프→프레임추출→검증. 완성샷 1장을 임시 파일로 저장해 그 경로 반환.
    (파일명은 나중에 recipe_id별로 복사하므로 여기선 video_id 임시명 사용.) 실패 시 None."""
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    video_path = ex.download_video(video_id)
    if not video_path:
        return None
    ts = ex.find_best_timestamp(client, video_path, recipe_name)
    if ts is None:
        return None
    tmp_path = THUMB_DIR / f"_tmp_{video_id}.jpg"
    if not ex.extract_frame_at(video_path, ts, tmp_path):
        return None
    try:
        if not ex.verify_frame(client, tmp_path, recipe_name):
            tmp_path.unlink(missing_ok=True)
            return None
    except Exception:
        tmp_path.unlink(missing_ok=True)
        return None
    return tmp_path


def find_recipe_ids(conn, video_id: str) -> list:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM service.recipes WHERE video_id = %s", (video_id,))
        return [r[0] for r in cur.fetchall()]


def wait_for_recipe_ids(conn, video_id: str) -> list:
    """recipe-main이 같은 이벤트를 먼저 적재할 때까지 제한시간 동안 기다린다."""
    deadline = time.monotonic() + DB_WAIT_SECONDS
    while True:
        recipe_ids = find_recipe_ids(conn, video_id)
        if recipe_ids:
            return recipe_ids
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return []
        time.sleep(min(DB_POLL_SECONDS, remaining))


def apply_thumbnail_for_ids(conn, tmp_path: Path, recipe_ids: list) -> int:
    """완성샷 임시파일을 각 recipe_id 파일명(/data/thumbnails/{id}.jpg)으로 복사하고
    각 레시피의 thumbnail_url을 그 경로로 UPDATE한다(기존 98건과 동일한 recipe_id 방식).
    한 영상에 레시피 여러 개면 같은 완성샷을 각 id로 복제한다."""
    updated = 0
    with conn.cursor() as cur:
        for rid in recipe_ids:
            final_path = THUMB_DIR / f"{rid}.jpg"
            shutil.copyfile(tmp_path, final_path)
            url = f"{URL_PREFIX}/{rid}.jpg"
            cur.execute(
                "UPDATE service.recipes SET thumbnail_url = %s WHERE id = %s",
                (url, rid),
            )
            updated += cur.rowcount
    conn.commit()
    tmp_path.unlink(missing_ok=True)   # 임시파일 제거
    return updated


def handle_message(msg: dict) -> None:
    video_id = msg["video_id"]
    recipe_name = msg.get("recipe_name") or video_id
    conn = db.connect()
    try:
        recipe_ids = wait_for_recipe_ids(conn, video_id)
        if not recipe_ids:
            raise RuntimeError(f"미적재 상태 — 재처리 필요: {video_id}")
        tmp_path = extract_frame_once(_bedrock(), video_id, recipe_name)
        if not tmp_path:
            print(f"완성샷 없음, 원본 유지: {video_id}")
            return
        updated = apply_thumbnail_for_ids(conn, tmp_path, recipe_ids)  # 내부에서 tmp 제거
        print(f"썸네일 갱신: {video_id} -> {updated}개 레시피 (recipe_id 파일명)")
    finally:
        conn.close()


def run() -> None:
    consumer = kafka_client.make_consumer(GROUP_THUMBNAIL)
    consumer.subscribe([TOPIC_PARSED])
    try:
        while True:
            rec = consumer.poll(1.0)
            if rec is None or rec.error():
                continue
            try:
                handle_message(json.loads(rec.value().decode("utf-8")))
                consumer.commit(rec)
            except Exception as e:
                # 실패 레코드에서 consumer 위치를 되돌려 다음 메시지가 앞 레코드를
                # 건너뛴 채 commit하는 것을 막는다.
                print(f"썸네일 처리 보류/실패: {e}")
                try:
                    consumer.seek(
                        TopicPartition(rec.topic(), rec.partition(), rec.offset())
                    )
                except Exception as seek_error:
                    # 리밸런싱 중이면 committed offset이 유지되므로 재할당 후 다시 받는다.
                    print(f"썸네일 offset 복구 대기: {seek_error}")
                time.sleep(RETRY_BACKOFF_SECONDS)
    finally:
        consumer.close()


if __name__ == "__main__":
    run()
