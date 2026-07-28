# -*- coding: utf-8 -*-
"""자립 복사본: data_pipeline/generate_thumbnails.py의 프레임 추출/검증 함수 +
프롬프트를 그대로 옮겨온 모듈. data_pipeline을 import하지 않는다(방식 B, 자립).

원본과 다른 점(의도적):
- CSV 기반 함수(load_rows/save_rows/process/main)는 옮기지 않음 — worker가 Kafka
  메시지 기반으로 대체.
- 원본의 OUT 기반 THUMB_DIR(상대경로, output/thumbnails)은 옮기지 않음 — worker가
  서버 마운트 경로(/data/thumbnails)를 직접 관리하고 extract_frame_at에 out_path를
  명시적으로 넘기므로 이 모듈은 THUMB_DIR을 필요로 하지 않는다.
- CACHE(영상 다운로드 캐시 디렉터리)는 download_video가 사용하므로 그대로 둔다.
"""
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import boto3


def log(msg):
    """Windows 콘솔(cp949 등)이 인코딩 못 하는 문자(이모지 등)가 레시피명에
    섞여 있어도 죽지 않도록 안전하게 출력한다."""
    enc = sys.stdout.encoding or "utf-8"
    print(msg.encode(enc, errors="replace").decode(enc, errors="replace"))


# 영상 임시 저장 캐시. 환경변수로 override 가능(도커: /tmp 등 쓰기 가능 경로).
# 자립형이라 data_pipeline을 참조하지 않는다.
CACHE = Path(os.environ.get("THUMB_CACHE_DIR", "/tmp/thumb_cache"))
CACHE.mkdir(parents=True, exist_ok=True)

# ffmpeg 실행 파일. 도커/리눅스는 PATH의 "ffmpeg", 로컬 윈도우는 환경변수로 지정.
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")

BEDROCK_REGION = "us-east-1"
NOVA_MODEL = "amazon.nova-pro-v1:0"

TIMESTAMP_PROMPT = (
    "이 요리 영상(레시피명: {name})에서 완성된 요리가 그릇에 담겨 가장 예쁘게 "
    "보이는 순간을 찾아주세요.\n\n"
    "가장 중요한 조건: 반드시 조리가 완전히 끝나고 최종적으로 그릇/접시에 "
    "담아낸 완성된 '음식 사진'이어야 합니다. 다음 장면은 절대 고르면 안 됩니다 - "
    "냄비나 팬 안에 있는 장면(뒤집개/젓가락/국자로 젓거나 뒤집는 중인 장면 "
    "포함), 빈 그릇, 재료 손질/계량 장면, 실험 결과표/그래프/수치 비교 화면, "
    "제품 포장/라벨만 보이는 화면. 팬이나 냄비가 화면에 보이거나 음식이 아닌 "
    "표/그래프/텍스트 슬라이드가 화면 대부분을 차지하면 그 순간은 후보에서 "
    "제외하세요.\n\n"
    "사람 얼굴이 화면 대부분을 차지하는 장면도 피해주세요. "
    "[광고] 표시처럼 화면 구석에 작게 있는 배지는 있어도 괜찮습니다. "
    "'{name} 완성!'처럼 레시피명과 연관된 자막도 자연스러우니 괜찮습니다. 다만 "
    "\"구독\", \"좋아요\", \"확인하세요\", \"고정댓글\"처럼 요리와 무관한 광고/구독 "
    "유도 문구가 화면 중앙을 가로지르는 순간은 피해주세요.\n\n"
    "중요: 위 조건에 완벽히 맞는 순간이 없다고 해서 그나마 비슷한 장면(표/그래프, "
    "얼굴 클로즈업, 냄비 안 등)을 억지로 고르지 마세요. 이 영상 전체를 통틀어 "
    "완성된 요리가 그릇/접시에 담겨 화면에 뚜렷하게 보이는 순간이 단 한 번도 "
    "없다면 반드시 NONE이라고만 답하세요. 차선책을 억지로 만들어내는 것보다 "
    "NONE이 훨씬 낫습니다.\n\n"
    "적합한 순간이 있으면 영상 시작부터 몇 초 지점인지 정수로만 답하세요"
    "(예: 23). 없으면 NONE이라고만 답하세요. 숫자 또는 NONE 외에 다른 말은 "
    "절대 하지 마세요."
)

TIMESTAMP_RE = re.compile(r'\d+')

VERIFY_PROMPT = (
    "레시피명: {name}\n"
    "이 이미지가 이 레시피의 완성된 요리를 그릇/접시에 담아 예쁘게 찍은 "
    "'완성 사진'이 맞습니까?\n"
    "다음 중 하나라도 해당하면 NO입니다: 조리 중인 장면(냄비/팬 안, 뒤집개/젓가락으로 "
    "젓는 중), 빈 그릇, 재료만 있는 장면, 실험 결과표/그래프/수치 화면, 사람 얼굴이 "
    "화면 대부분을 차지하는 장면, 이미 한 입 베어 먹은 자국이 있거나 손으로 집어서 "
    "먹는 중인 장면(음식이 온전한 형태가 아니라 뜯기거나 베어 물린 상태).\n"
    "요리가 온전하고 완성된 형태로 접시/그릇에 담겨 화면에 뚜렷하게 보이면 "
    "YES입니다 (자막이 있어도 무방, 손으로 온전한 상태로 들고 있는 것도 무방).\n"
    "YES 또는 NO 한 단어로만 답하세요."
)


def download_video(video_id):
    out_path = CACHE / f"{video_id}.mp4"
    if out_path.exists():
        return out_path
    r = subprocess.run(
        ["python", "-m", "yt_dlp", f"https://youtube.com/watch?v={video_id}",
         "-f", "best", "-o", str(out_path), "--no-warnings"],
        capture_output=True, text=True, timeout=90,
    )
    if r.returncode != 0 or not out_path.exists():
        return None
    return out_path


def find_best_timestamp(client, video_path, recipe_name):
    """영상을 Nova Pro에 실어 완성샷 타임스탬프(초)를 받는다. 없으면 None."""
    video_bytes = video_path.read_bytes()
    body = json.dumps({
        "messages": [{
            "role": "user",
            "content": [
                {"video": {"format": "mp4", "source": {"bytes": base64.b64encode(video_bytes).decode("utf-8")}}},
                {"text": TIMESTAMP_PROMPT.format(name=recipe_name)},
            ],
        }],
        "inferenceConfig": {"maxTokens": 20},
    })
    resp = client.invoke_model(
        modelId=NOVA_MODEL, body=body,
        contentType="application/json", accept="application/json",
    )
    result = json.loads(resp["body"].read())
    text = result["output"]["message"]["content"][0]["text"].strip()
    if "NONE" in text.upper():
        return None
    m = TIMESTAMP_RE.search(text)
    if not m:
        return None
    return int(m.group())


def extract_frame_at(video_path, timestamp_sec, out_path):
    hh = timestamp_sec // 3600
    mm = (timestamp_sec % 3600) // 60
    ss = timestamp_sec % 60
    ts = f"{hh:02d}:{mm:02d}:{ss:02d}"
    r = subprocess.run(
        [FFMPEG_BIN, "-ss", ts, "-i", str(video_path),
         "-vframes", "1", "-q:v", "2", "-y", str(out_path)],
        capture_output=True, timeout=30,
    )
    return out_path.exists()


def verify_frame(client, image_path, recipe_name):
    """추출된 프레임이 실제로 완성샷 조건에 맞는지 재확인. 1단계 타임스탬프
    판별이 후보를 억지로 골라 NONE을 피하는 경향이 있어(Gemini/Nova Lite
    테스트에서 공통 확인됨) 별도 이미지 판별 단계로 한 번 더 거른다."""
    image_bytes = image_path.read_bytes()
    body = json.dumps({
        "messages": [{
            "role": "user",
            "content": [
                {"image": {"format": "jpeg", "source": {"bytes": base64.b64encode(image_bytes).decode("utf-8")}}},
                {"text": VERIFY_PROMPT.format(name=recipe_name)},
            ],
        }],
        "inferenceConfig": {"maxTokens": 10},
    })
    resp = client.invoke_model(
        modelId=NOVA_MODEL, body=body,
        contentType="application/json", accept="application/json",
    )
    result = json.loads(resp["body"].read())
    text = result["output"]["message"]["content"][0]["text"].strip().upper()
    return "YES" in text
