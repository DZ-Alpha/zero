# -*- coding: utf-8 -*-
"""
producer 자립형 발견+추출+게이트 모듈. data_pipeline/run_pipeline.py와
data_pipeline/run_pipeline_text_only.py에서 필요한 함수·프롬프트·상수만
바이트 단위로 동일하게 복사해 자립시켰다 (whisper 등 무거운 의존성은 제외).

복사 원본:
- data_pipeline/run_pipeline.py: yt_api_call, parse_iso8601_duration,
  fetch_description_and_comments, YT_KEY
- data_pipeline/run_pipeline_text_only.py: discover_since_cursor,
  build_user_text, call_llm, parse_json_response, passes_quality_gate,
  TEXT_ONLY_PROMPT, MODEL_ID, INITIAL_LOOKBACK_HOURS, PERIODIC_LIMIT, MIN_STEPS

LLM 호출은 Anthropic 직접 API 대신 AWS Bedrock invoke_model을 쓴다
(Anthropic 토큰 소진 대응). 모델은 원 설계대로 Haiku 4.5 유지.
"""
import json, re, time
from pathlib import Path
from datetime import datetime, timezone

import os
import boto3

# YOUTUBE_API_KEY2를 얻는다.
# 1순위: os.environ (도커 env_file 주입 / 이미 로드된 환경변수)
# 2순위: .env 파일 상위탐색(로컬 개발 시). 파일이 없어도 실패하지 않는다.
def _load_yt_key():
    key = os.environ.get("YOUTUBE_API_KEY2")
    if key:
        return key.strip()
    for _p in [Path(__file__).resolve(), *Path(__file__).resolve().parents][:7]:
        env = _p / ".env"
        if env.is_file():
            m = re.search(r'^YOUTUBE_API_KEY2\s*=\s*(.+)$', env.read_text(encoding="utf-8"), re.M)
            if m:
                return m.group(1).strip()
    raise RuntimeError("YOUTUBE_API_KEY2를 환경변수/.env 어디에서도 찾지 못했습니다")

YT_KEY = _load_yt_key()

# Anthropic 직접 API 토큰 소진으로 Bedrock으로 전환. 모델은 원 설계대로 Haiku 4.5 유지.
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-2")
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)


def yt_api_call(endpoint, params, retries=5):
    import urllib.parse, urllib.request, urllib.error, ssl
    ctx = ssl.create_default_context()
    qs = urllib.parse.urlencode(params)
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                result = json.loads(r.read().decode("utf-8"))
            time.sleep(0.3)  # 요청 간 간격을 둬서 레이트리밋 회피
            return result
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = 2 ** (attempt + 1)  # 2,4,8,16,32초 지수 백오프
                print(f"    (429 Too Many Requests, {wait}초 대기 후 재시도 {attempt+1}/{retries})")
                time.sleep(wait)
                continue
            raise


def parse_iso8601_duration(s):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', s)
    if not m:
        return None
    h, mn, sec = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mn * 60 + sec


def fetch_description_and_comments(video_id, max_comments=5):
    """스펙 §9.8: 설명란 + 상위 댓글을 조회. 크리에이터가 직접 정리한 정량/재료
    텍스트가 있으면 Vision/Whisper보다 신뢰도가 높은 정보원."""
    description = ""
    comments = []
    try:
        vdata = yt_api_call("videos", {"part": "snippet", "id": video_id, "key": YT_KEY})
        items = vdata.get("items", [])
        if items:
            description = items[0]["snippet"].get("description", "")
    except Exception:
        pass
    try:
        cdata = yt_api_call("commentThreads", {
            "part": "snippet", "videoId": video_id, "maxResults": max_comments,
            "order": "relevance", "key": YT_KEY,
        })
        for it in cdata.get("items", []):
            text = it["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            comments.append(text)
    except Exception:
        pass  # 댓글 비활성화된 영상 등은 조용히 건너뜀
    return description, comments


INITIAL_LOOKBACK_HOURS = 24  # 커서 파일이 없는 최초 실행에서만 사용하는 안전 lookback
PERIODIC_LIMIT = 200  # 한 폴링 구간(보통 ~1시간치) 신규 숏츠 상한 — 여유 있게 크게 잡음


def discover_since_cursor(limit, since):
    """주기적 수집용: publishedAfter=since(커서) ~ 지금까지만 조회한다
    (스펙 §2 ② — 하루 고정 창이 아니라 마지막 수집 시각부터 슬라이딩)."""
    now = datetime.now(timezone.utc)
    params = {
        "part": "snippet", "q": "저당 레시피", "type": "video", "order": "date",
        "publishedAfter": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "publishedBefore": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "maxResults": 50, "regionCode": "KR", "relevanceLanguage": "ko", "key": YT_KEY,
    }
    data = yt_api_call("search", params)
    all_items = {}
    for it in data.get("items", []):
        vid = it["id"].get("videoId")
        if vid and vid not in all_items:
            all_items[vid] = {
                "video_id": vid,
                "title": it["snippet"]["title"],
                "published_at": it["snippet"]["publishedAt"],
            }

    ids = list(all_items.keys())
    # duration 확인해서 숏폼만
    shorts = []
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        vdata = yt_api_call("videos", {"part": "contentDetails", "id": ",".join(batch), "key": YT_KEY})
        for it in vdata.get("items", []):
            dur = parse_iso8601_duration(it["contentDetails"]["duration"])
            if dur is not None and dur <= 61:
                entry = all_items[it["id"]]
                entry["duration_sec"] = dur
                shorts.append(entry)
            if len(shorts) >= limit:
                break
        if len(shorts) >= limit:
            break
    return shorts[:limit], now

TEXT_ONLY_PROMPT = """당신은 저당 레시피 유튜브 숏츠의 설명란과 댓글 텍스트만 보고
레시피 정보를 추출하는 도구입니다. 영상 프레임이나 음성은 제공되지 않습니다.

먼저 확인할 것 — 변형 레시피(버전) 감지:
- 하나의 영상 설명란에 재료 구성이 서로 다른 레시피 버전이 여러 개 들어있는 경우가 있습니다.
  (예: "코코넛밀크 버전"과 "연유 버전"처럼 조리 단계는 공통이지만 특정 재료만 바뀌는 경우,
  또는 재료와 단계가 완전히 별개인 두 레시피가 한 설명란에 같이 적힌 경우)
- 이런 경우 절대로 두 버전의 재료를 하나로 합치지 마세요. 각 버전을 별도의 레시피로 분리하세요.
- 조리 단계가 공통 단계 + 버전별로 갈라지는 단계로 되어 있으면, 공통 단계는 각 버전의 steps에
  동일하게 포함하고 갈라지는 부분만 버전별로 다르게 적으세요.
- 버전이 여러 개면 recipe_name에 구분되는 이름을 붙이세요 (예: "브라질리안 레모네이드 (코코넛밀크 버전)").
- 변형이 없는 평범한 단일 레시피면 recipes 배열에 항목을 1개만 넣으세요.

완전성 판단 기준 (레시피 버전마다 각각 판단):
- 설명란/댓글에 (1)재료명 전체 목록, (2)각 재료의 정량, (3)조리 단계(순서)가
  전부 명시되어 있는지 판단하세요.
- 셋 중 하나라도 빠지거나 불완전하면 그 버전의 is_complete를 false로 반환하세요.
  (예: 재료 목록은 있지만 정량이 하나도 없음 / 조리법이 텍스트에 없음 등)
- 실제로 텍스트에 적힌 내용만 사용하세요. 추측하거나 표준값으로 채우지 마세요.
  화면/음성은 제공되지 않으므로 텍스트에 없는 정량을 절대 추정하지 마세요.

완전한 레시피(is_complete=true)에 한해 각 재료를 다음 중 하나로 분류하세요
(반드시 텍스트에 실제 등장한 재료만 분류 대상입니다):
- "substituted": 저당/제로 등 대체 식재료 (예: 알룰로스, 저당 고추장, 곤약면)
- "common": 저당화와 무관한 일반 재료 (예: 양파, 대파, 마늘)
절대 "base"로 분류하지 마세요. base(대체 전 원래 재료, 예: 설탕/밀가루)는 텍스트에
등장하지 않는 가상의 재료이므로 이 단계에서는 추출 대상이 아닙니다.

다음 JSON 형식으로만 응답하세요 (설명 문구 없이 JSON만):
{
  "recipes": [
    {
      "recipe_name": "레시피명 (버전이 있으면 버전 구분 포함) 또는 null",
      "is_complete": true 또는 false,
      "incomplete_reason": "불완전한 이유 (완전하면 null)",
      "steps": ["조리 단계 문구들"],
      "ingredients": [
        {"name": "...", "amount": "...", "ingredient_type": "substituted 또는 common만 (base 금지)"}
      ]
    }
  ]
}
"""

MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"  # Bedrock inference profile

MIN_STEPS = 3  # steps가 이보다 적으면(2건 이하) 저장하지 않음


def build_user_text(title, description, comments):
    parts = [f"영상 제목: {title}"]
    if description.strip():
        parts.append(f"\n영상 설명란:\n{description}")
    if comments:
        joined = "\n---\n".join(comments)
        parts.append(f"\n상위 댓글 {len(comments)}개:\n{joined}")
    parts.append("\n위 정보만 보고 JSON으로만 응답하세요.")
    return "\n".join(parts)


def call_llm(user_text):
    # Bedrock invoke_model (Anthropic 직접 API 토큰 소진으로 전환). 프롬프트·모델(Haiku 4.5) 동일.
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "system": TEXT_ONLY_PROMPT,
        "messages": [{"role": "user", "content": user_text}],
    })
    resp = bedrock.invoke_model(modelId=MODEL_ID, body=body)
    out = json.loads(resp["body"].read())
    return "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")


def parse_json_response(raw):
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1]
        s = s.rsplit("```", 1)[0]
    return json.loads(s)


def passes_quality_gate(steps, ingredients):
    """완전성 판단(is_complete)을 이미 통과한 레시피만 여기 들어온다.
    steps가 부실하면(<=2건) 그래도 걸러낸다."""
    if len(steps) <= 2:
        return False, "steps <= 2"
    if not ingredients:
        return False, "재료 없음"
    return True, ""
