"""Dump Gemini's raw reply for specific MinIO objects.

Diagnostic only: it answers whether an empty list-diet came from the model or
from the worker's normalization step. Run inside dangdang-pipeline-worker,
which already holds GEMINI_API_KEY.
"""
from __future__ import annotations

import base64
import json
import os
import sys

from minio import Minio

from app.vision import _GEMINI_PROMPT, _post_json, _safe_mime_type, normalize_result, read_minio_object


def main(keys: list[str]) -> int:
    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )
    model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    for key in keys:
        print(f"\n===== {key} =====")
        image, content_type = read_minio_object(client, os.environ["MINIO_BUCKET"], key, 10 * 1024 * 1024)
        payload = {
            "contents": [{"parts": [
                {"text": _GEMINI_PROMPT},
                {"inline_data": {"mime_type": _safe_mime_type(content_type, key),
                                 "data": base64.b64encode(image).decode("ascii")}},
            ]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        response = _post_json(endpoint, payload, {"X-goog-api-key": os.environ["GEMINI_API_KEY"]}, 30)

        for candidate in response.get("candidates", []):
            print("finishReason :", candidate.get("finishReason"))
            if candidate.get("safetyRatings"):
                print("safetyRatings:", json.dumps(candidate["safetyRatings"], ensure_ascii=False))
            text = "".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", [])
                           if isinstance(p, dict))
            print("raw text     :", text[:600])
        if response.get("promptFeedback"):
            print("promptFeedback:", json.dumps(response["promptFeedback"], ensure_ascii=False))
        print("usage        :", json.dumps(response.get("usageMetadata", {}), ensure_ascii=False))

        try:
            text = "".join(p.get("text", "") for c in response["candidates"]
                           for p in c["content"]["parts"] if isinstance(p, dict))
            parsed = json.loads(text)
            print("model items  :", len(parsed.get("list-diet", [])))
            print("normalized   :", len(normalize_result(parsed, provider="gemini")["list-diet"]))
        except Exception as exc:  # diagnostic script: report and continue
            print("parse failed :", type(exc).__name__, exc)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
