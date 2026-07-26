"""Submit a burst of real photographs to measure the deployed Gemini path.

Runs inside dangdang-pipeline-api. Reports the outcome distribution and the
per-request latency so quota behaviour and the retry path can be observed under
sustained load. Prints a JSON summary on the last line.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone

from minio import Minio

API = os.getenv("E2E_API", "http://127.0.0.1:8080")
BUCKET = os.environ["MINIO_BUCKET"]
SOURCE_PREFIX = os.getenv("LOAD_SOURCE_PREFIX", "vision-qa/food101-20260720")
COUNT = int(os.getenv("LOAD_COUNT", "40"))
RUN = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
TIMEOUT = int(os.getenv("LOAD_TIMEOUT_SECONDS", "600"))


def api(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{API}{path}", data=data, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode(errors="replace")[:200]}


def main() -> int:
    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )

    print(f"submitting {COUNT} photographs as fast as the API accepts them", flush=True)
    pending = {}
    for index in range(COUNT):
        token = f"load-{RUN}-{index}"
        key = f"vision-qa/load-{RUN}/{index}.jpg"
        response = client.get_object(BUCKET, f"{SOURCE_PREFIX}/{index}.jpg")
        try:
            payload = response.read()
        finally:
            response.close()
            response.release_conn()
        client.put_object(BUCKET, key, io.BytesIO(payload), len(payload), content_type="image/jpeg")

        ref = f"minio://{BUCKET}/{key}"
        status, _ = api("POST", f"/b/diet/upload?usr={token}", {"img": ref, "mode": "daily"})
        if status != 200:
            print(f"  upload rejected index={index} status={status}", flush=True)
            continue
        status, analysis = api("POST", f"/b/diet/ai-analyze?usr={token}", {"img": ref})
        if status not in (200, 202):
            print(f"  analyze rejected index={index} status={status}", flush=True)
            continue
        pending[analysis["id"]] = token

    submitted_at = time.time()
    print(f"submitted {len(pending)} analyses in {submitted_at - submitted_at:.0f}s; waiting for completion", flush=True)

    outcomes: dict[str, dict] = {}
    deadline = time.time() + TIMEOUT
    while pending and time.time() < deadline:
        for analysis_id, token in list(pending.items()):
            _, payload = api("GET", f"/b/diet/ai-analyze?id={analysis_id}&usr={token}")
            if payload.get("status") in {"DONE", "FAILED"}:
                payload["elapsed"] = round(time.time() - submitted_at, 1)
                outcomes[analysis_id] = payload
                del pending[analysis_id]
        if pending:
            time.sleep(2)

    total_seconds = time.time() - submitted_at
    statuses = Counter(o.get("status") for o in outcomes.values())
    errors = Counter(o.get("error") for o in outcomes.values() if o.get("status") == "FAILED")
    confirmations = sum(1 for o in outcomes.values() if o.get("needs_user_confirmation"))
    empty = sum(1 for o in outcomes.values() if o.get("status") == "DONE" and not o.get("list-diet"))

    print(f"\n처리 {len(outcomes)}건 / 미완료 {len(pending)}건, 총 {total_seconds:.0f}초", flush=True)
    print(f"  상태 분포      : {dict(statuses)}", flush=True)
    print(f"  실패 코드      : {dict(errors) if errors else '없음'}", flush=True)
    print(f"  확인 필요 분기 : {confirmations}건 (그중 음식 미검출 {empty}건)", flush=True)
    if outcomes:
        throughput = len(outcomes) / total_seconds * 60 if total_seconds else 0
        print(f"  실측 처리율    : 분당 {throughput:.1f}건", flush=True)

    print("LOAD_SUMMARY " + json.dumps({
        "submitted": len(pending) + len(outcomes), "completed": len(outcomes),
        "unfinished": len(pending), "seconds": round(total_seconds, 1),
        "statuses": dict(statuses), "errors": dict(errors),
        "needs_confirmation": confirmations, "empty_results": empty,
    }, ensure_ascii=False))
    return 0 if not pending else 1


if __name__ == "__main__":
    sys.exit(main())
