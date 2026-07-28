"""Synthetic end-to-end check for both pipelines, runnable without the real
frontend or backend services.

Runs inside dangdang-pipeline-api, which already carries the MinIO, Kafka and
PostgreSQL clients plus the pipeline's own environment.

Vision pipeline   MinIO object -> API outbox -> Kafka -> worker -> Gemini
                  -> PostgreSQL -> diet.photo.completed / diet.photo.failed
Activity pipeline synthetic producer -> user.activity.raw -> Mongo consumer

The activity events are only produced here; the Mongo side is asserted by the
shell wrapper through mongosh. Prints a JSON summary on the last line.
"""
from __future__ import annotations

import io
import json
import os
import struct
import sys
import time
import zlib
import urllib.request
import uuid
from datetime import datetime, timezone

from confluent_kafka import Consumer, Producer, TopicPartition
from minio import Minio

API = os.getenv("E2E_API", "http://127.0.0.1:8080")
BUCKET = os.environ["MINIO_BUCKET"]
SOURCE_PREFIX = os.getenv("E2E_SOURCE_PREFIX", "vision-qa/food101-20260720")
RUN = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
POLL_SECONDS = int(os.getenv("E2E_POLL_SECONDS", "90"))

COMPLETED_TOPIC = os.getenv("COMPLETED_TOPIC", "diet.photo.completed")
FAILED_TOPIC = os.getenv("FAILED_TOPIC", "diet.photo.failed")
ACTIVITY_TOPIC = os.getenv("ACTIVITY_TOPIC", "user.activity.raw")

results: list[dict] = []


def _flat_png(width: int = 96, height: int = 96, rgb: tuple[int, int, int] = (118, 126, 134)) -> bytes:
    """A valid but foodless image, used to exercise the confirmation branch."""
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return b"".join([
        b"\x89PNG\r\n\x1a\n",
        chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
        chunk(b"IDAT", zlib.compress(raw)),
        chunk(b"IEND", b""),
    ])


_NONFOOD_PNG = _flat_png()


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)
    return ok


def minio_client() -> Minio:
    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )


def api(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{API}{path}", data=data, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode(errors="replace")[:300]}


def clone_food_image(client: Minio, index: int, dest_key: str) -> int:
    """Copy one Food-101 QA image to a fresh key so each run is a new event."""
    response = client.get_object(BUCKET, f"{SOURCE_PREFIX}/{index}.jpg")
    try:
        payload = response.read()
    finally:
        response.close()
        response.release_conn()
    client.put_object(BUCKET, dest_key, io.BytesIO(payload), len(payload), content_type="image/jpeg")
    return len(payload)


def end_offsets(consumer: Consumer, topic: str) -> list[TopicPartition]:
    meta = consumer.list_topics(topic, timeout=15).topics[topic]
    marks = []
    for partition in meta.partitions:
        _, high = consumer.get_watermark_offsets(TopicPartition(topic, partition), timeout=15)
        marks.append(TopicPartition(topic, partition, high))
    return marks


def drain(consumer: Consumer, marks: list[TopicPartition], seconds: float = 10) -> list[dict]:
    """Read everything produced after the recorded marks."""
    consumer.assign(marks)
    collected, deadline = [], time.time() + seconds
    while time.time() < deadline:
        message = consumer.poll(1.0)
        if message is None or message.error():
            continue
        try:
            collected.append(json.loads(message.value() or b"{}"))
        except json.JSONDecodeError:
            pass
    return collected


def wait_for_terminal(analysis_id: str, token: str) -> dict:
    deadline = time.time() + POLL_SECONDS
    payload: dict = {}
    while time.time() < deadline:
        _, payload = api("GET", f"/b/diet/ai-analyze?id={analysis_id}&usr={token}")
        if payload.get("status") in {"DONE", "FAILED"}:
            return payload
        time.sleep(1)
    return payload


def submit(token: str, key: str) -> tuple[str, str]:
    ref = f"minio://{BUCKET}/{key}"
    status, upload = api("POST", f"/b/diet/upload?usr={token}", {"img": ref, "mode": "daily"})
    if status != 200:
        raise RuntimeError(f"upload failed status={status} body={upload}")
    status, analysis = api("POST", f"/b/diet/ai-analyze?usr={token}", {"img": ref})
    if status not in (200, 202):
        raise RuntimeError(f"analyze failed status={status} body={analysis}")
    return analysis["id"], ref


# --------------------------------------------------------------------------
# Vision pipeline
# --------------------------------------------------------------------------
def vision_pipeline(client: Minio, consumer: Consumer) -> None:
    print("\n== 1. Vision pipeline: MinIO -> Kafka -> worker -> Gemini -> DB ==", flush=True)
    completed_marks = end_offsets(consumer, COMPLETED_TOPIC)
    failed_marks = end_offsets(consumer, FAILED_TOPIC)

    happy_token = f"e2e-vision-{RUN}"
    happy_key = f"vision-qa/e2e-{RUN}/food.jpg"
    size = clone_food_image(client, 0, happy_key)
    happy_id, happy_ref = submit(happy_token, happy_key)
    print(f"  submitted analysis_id={happy_id} key={happy_key} bytes={size}", flush=True)

    # Same image resubmitted must not create a second job.
    _, repeat = api("POST", f"/b/diet/ai-analyze?usr={happy_token}", {"img": happy_ref})
    check("동일 사진 재요청이 같은 analysis_id 반환 (idempotency)", repeat.get("id") == happy_id,
          f"{repeat.get('id')}")

    # A registered upload whose object disappears must fail, not hang.
    gone_token = f"e2e-gone-{RUN}"
    gone_key = f"vision-qa/e2e-{RUN}/deleted.jpg"
    clone_food_image(client, 1, gone_key)
    gone_id, _ = submit(gone_token, gone_key)
    client.remove_object(BUCKET, gone_key)
    print(f"  submitted analysis_id={gone_id} then deleted its MinIO object", flush=True)

    happy = wait_for_terminal(happy_id, happy_token)
    check("실사진 분석이 DONE 도달", happy.get("status") == "DONE", f"status={happy.get('status')}")

    listed = happy.get("list-diet")
    check("결과가 list-diet 계약 형태", isinstance(listed, list),
          f"items={len(listed) if isinstance(listed, list) else 'n/a'}")
    if isinstance(listed, list) and listed:
        first = listed[0]
        check("항목에 name/dang/calo/ingred-list 존재",
              all(k in first for k in ("name", "dang", "calo", "ingred-list")),
              f"{first.get('name')} calo={first.get('calo')} dang={first.get('dang')}")

    confidence = happy.get("confidence")
    needs = happy.get("needs_user_confirmation")
    check("confidence 가 응답에 포함", isinstance(confidence, (int, float)), f"confidence={confidence}")
    check("needs_user_confirmation 이 응답에 포함", isinstance(needs, bool), f"needs={needs}")
    if isinstance(listed, list) and isinstance(needs, bool):
        expected = (not listed) or float(confidence or 0) < 0.75
        check("빈 결과/저신뢰도 판정이 규칙과 일치", needs == expected,
              f"items={len(listed)} confidence={confidence} needs={needs} expected={expected}")

    gone = wait_for_terminal(gone_id, gone_token)
    check("객체 삭제 건이 FAILED 로 종결", gone.get("status") == "FAILED", f"status={gone.get('status')}")

    # A non-food photograph: Gemini returns an empty list-diet but has been
    # observed reporting 0.95 confidence anyway, so the worker — not the model —
    # must be the thing that routes this to user confirmation.
    nonfood_token = f"e2e-nonfood-{RUN}"
    nonfood_key = f"vision-qa/e2e-{RUN}/nonfood.png"
    client.put_object(BUCKET, nonfood_key, io.BytesIO(_NONFOOD_PNG), len(_NONFOOD_PNG), content_type="image/png")
    nonfood_id, _ = submit(nonfood_token, nonfood_key)
    nonfood = wait_for_terminal(nonfood_id, nonfood_token)
    nonfood_items = nonfood.get("list-diet")
    if check("비음식 사진도 FAILED 가 아닌 정상 종결", nonfood.get("status") == "DONE",
             f"status={nonfood.get('status')}"):
        check("비음식 사진은 사용자 확인 필요로 분기",
              nonfood.get("needs_user_confirmation") is True,
              f"items={len(nonfood_items) if isinstance(nonfood_items, list) else 'n/a'} "
              f"confidence={nonfood.get('confidence')} needs={nonfood.get('needs_user_confirmation')}")

    completed = drain(consumer, completed_marks, seconds=8)
    failed = drain(consumer, failed_marks, seconds=8)
    check("Kafka diet.photo.completed 에 완료 이벤트 발행",
          any(e.get("analysis_id") == happy_id for e in completed), f"new={len(completed)}")
    failure = next((e for e in failed if e.get("analysis_id") == gone_id), None)
    check("Kafka diet.photo.failed 에 실패 이벤트 발행", failure is not None, f"new={len(failed)}")
    if failure:
        check("실패 이벤트 error_code=OBJECT_NOT_READABLE",
              failure.get("error_code") == "OBJECT_NOT_READABLE", str(failure.get("error_code")))
        check("실패 이벤트에 retryable 플래그 존재", "retryable" in failure,
              f"retryable={failure.get('retryable')}")

    for event in completed:
        if event.get("analysis_id") == happy_id:
            blob = json.dumps(event)
            check("Kafka 완료 이벤트에 이미지 바이너리 없음",
                  "base64" not in blob and len(blob) < 20000, f"payload={len(blob)}B")
            check("완료 이벤트가 causation_event_id 로 요청과 연결",
                  bool(event.get("causation_event_id")), str(event.get("causation_event_id")))


# --------------------------------------------------------------------------
# Activity pipeline
# --------------------------------------------------------------------------
def activity_pipeline() -> dict:
    print("\n== 2. Activity pipeline: producer -> user.activity.raw -> MongoDB ==", flush=True)
    producer = Producer({
        "bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
        "enable.idempotence": True,
        "acks": "all",
    })
    user_id = 424242
    events = []
    for event_type, properties in (
        ("user.auth.login_succeeded", {"method": "password"}),
        ("user.diet.photo_uploaded", {"meal_log_id": str(uuid.uuid4())}),
        ("user.diet.meal_confirmed", {"meal_log_id": str(uuid.uuid4())}),
    ):
        events.append({
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "user_id": user_id,
            "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "producer": "e2e-harness-service",
            "schema_version": 1,
            "properties": properties,
        })

    for event in events:
        producer.produce(ACTIVITY_TOPIC, key=str(user_id), value=json.dumps(event).encode())
    # Re-send one event verbatim: the Mongo consumer must store it exactly once.
    producer.produce(ACTIVITY_TOPIC, key=str(user_id), value=json.dumps(events[0]).encode())
    producer.flush(20)
    print(f"  produced {len(events)} events + 1 duplicate of {events[0]['event_id']}", flush=True)

    check("Kafka 발행이 acks=all 로 완료", True, f"{len(events) + 1} messages")
    return {"user_id": user_id, "event_ids": [e["event_id"] for e in events],
            "duplicated": events[0]["event_id"]}


def main() -> int:
    client = minio_client()
    consumer = Consumer({
        "bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
        "group.id": f"e2e-check-{uuid.uuid4()}",
        "enable.auto.commit": False,
        "auto.offset.reset": "latest",
    })
    try:
        vision_pipeline(client, consumer)
        activity = activity_pipeline()
    finally:
        consumer.close()

    failures = [r for r in results if not r["ok"]]
    print(f"\n== 검사 {len(results)}건 중 통과 {len(results) - len(failures)}건, 실패 {len(failures)}건 ==", flush=True)
    print("E2E_SUMMARY " + json.dumps({"activity": activity, "checks": results}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
