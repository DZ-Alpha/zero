"""Compare Gemini models against the non-user Vision QA photographs in MinIO.

Run inside an event-pipeline pod so credentials never leave the cluster:

    python /tmp/vision_model_benchmark.py gemini-flash-latest gemini-3.5-flash-lite
"""
from __future__ import annotations

import base64
import json
import os
import statistics
import sys
import time
from collections import Counter

from minio import Minio

from app.vision import (
    _GEMINI_PROMPT,
    _GEMINI_RESPONSE_SCHEMA,
    _parse_json_text,
    _post_json,
    _safe_mime_type,
    normalize_result,
    read_minio_object,
)


SOURCE_PREFIX = os.getenv("BENCHMARK_SOURCE_PREFIX", "vision-qa/food101-20260720")
COUNT = int(os.getenv("BENCHMARK_COUNT", "10"))
TIMEOUT_SECONDS = float(os.getenv("BENCHMARK_TIMEOUT_SECONDS", "15"))


def generation_config(model: str) -> dict:
    config = {
        "responseMimeType": "application/json",
        "responseJsonSchema": _GEMINI_RESPONSE_SCHEMA,
        "maxOutputTokens": 4096,
    }
    if model.startswith("gemini-3") or model == "gemini-flash-latest":
        config["thinkingConfig"] = {"thinkingLevel": "minimal"}
    else:
        config["temperature"] = 0
        config["thinkingConfig"] = {"thinkingBudget": 512}
    return config


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percent))
    return ordered[index]


def main(models: list[str]) -> int:
    if not models:
        raise SystemExit("pass at least one Gemini model ID")
    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )
    summaries = []
    for model in models:
        latencies: list[float] = []
        outcomes = Counter()
        print(f"MODEL {model}", flush=True)
        for index in range(COUNT):
            key = f"{SOURCE_PREFIX}/{index}.jpg"
            image, content_type = read_minio_object(
                client, os.environ["MINIO_BUCKET"], key, 10 * 1024 * 1024,
            )
            payload = {
                "contents": [{"parts": [
                    {"text": _GEMINI_PROMPT},
                    {"inline_data": {
                        "mime_type": _safe_mime_type(content_type, key),
                        "data": base64.b64encode(image).decode("ascii"),
                    }},
                ]}],
                "generationConfig": generation_config(model),
            }
            started = time.monotonic()
            try:
                response = _post_json(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    payload,
                    {"X-goog-api-key": os.environ["GEMINI_API_KEY"]},
                    TIMEOUT_SECONDS,
                )
                text = "".join(
                    part.get("text", "")
                    for candidate in response["candidates"]
                    for part in candidate["content"]["parts"]
                    if isinstance(part, dict)
                )
                result = normalize_result(_parse_json_text(text), provider="gemini")
                elapsed = round(time.monotonic() - started, 3)
                latencies.append(elapsed)
                names = [item["name"] for item in result["list-diet"]]
                outcome = "ok" if names else "empty"
                outcomes[outcome] += 1
                print(json.dumps({
                    "index": index, "seconds": elapsed, "outcome": outcome,
                    "names": names, "confidence": result["confidence"],
                }, ensure_ascii=False), flush=True)
            except Exception as exc:
                elapsed = round(time.monotonic() - started, 3)
                outcomes[type(exc).__name__] += 1
                print(json.dumps({
                    "index": index, "seconds": elapsed,
                    "outcome": type(exc).__name__,
                }), flush=True)
        summary = {
            "model": model,
            "count": COUNT,
            "outcomes": dict(outcomes),
            "mean_seconds": round(statistics.mean(latencies), 3) if latencies else None,
            "p50_seconds": round(percentile(latencies, 0.50), 3) if latencies else None,
            "p95_seconds": round(percentile(latencies, 0.95), 3) if latencies else None,
        }
        summaries.append(summary)
        print("SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    print("BENCHMARK_SUMMARY " + json.dumps(summaries, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
