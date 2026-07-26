# -*- coding: utf-8 -*-
import json, shutil, time
from pathlib import Path

import boto3

from kafka.config import TOPIC_PARSED, GROUP_THUMBNAIL
from kafka.common import kafka_client, db
from kafka.thumbnail import extract_lib as ex   # 자립 복사 모듈

# 컨테이너 내부 경로. compose가 호스트 /opt/zero-infra/data/thumbnails 를 여기에 마운트한다.
THUMB_DIR = Path("/data/thumbnails")
# DB thumbnail_url에 저장하는 경로 형태(기존 98건과 통일: /data/thumbnails/{recipe_id}.jpg)
URL_PREFIX = "/data/thumbnails"
FIND_RETRIES = 3
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
    tmp_path = extract_frame_once(_bedrock(), video_id, recipe_name)
    if not tmp_path:
        print(f"완성샷 없음, 원본 유지: {video_id}")
        return
    conn = db.connect()
    try:
        recipe_ids = []
        for _ in range(FIND_RETRIES):
            recipe_ids = find_recipe_ids(conn, video_id)
            if recipe_ids:
                break
            time.sleep(2)   # 아직 미적재면 짧게 대기 후 재조회
        if not recipe_ids:
            # 미적재면 tmp 정리 후 재처리(커밋 안 됨). 재처리 때 다시 추출한다.
            tmp_path.unlink(missing_ok=True)
            raise RuntimeError(f"미적재 상태 — 재처리 필요: {video_id}")
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
                # 썸네일 실패는 정상(완성샷 없음 등) — DLQ 안 감. 미적재만 재처리(커밋 안 함).
                print(f"썸네일 처리 보류/실패: {e}")
    finally:
        consumer.close()


if __name__ == "__main__":
    run()
