from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = 1


def uuid7() -> uuid.UUID:
    """Generate an RFC 9562 UUIDv7 without a third-party dependency."""
    unix_ms = int(time.time() * 1000)
    rand = uuid.uuid4().int
    value = (unix_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= (rand >> 64 & 0xFFF) << 64
    value |= 0b10 << 62
    value |= rand & ((1 << 62) - 1)
    return uuid.UUID(int=value)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def requested_event(
    *,
    event_id: uuid.UUID,
    analysis_id: uuid.UUID,
    upload_id: uuid.UUID,
    user_id: str,
    image_key: str,
) -> dict[str, Any]:
    return {
        "event_id": str(event_id),
        "analysis_id": str(analysis_id),
        "upload_id": str(upload_id),
        "user_id": user_id,
        "image_key": image_key,
        "requested_at": utc_now(),
        "schema_version": SCHEMA_VERSION,
    }


def validate_requested_event(event: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError("event must be a JSON object")
    required = {
        "event_id", "analysis_id", "upload_id", "user_id",
        "image_key", "requested_at", "schema_version",
    }
    missing = sorted(required.difference(event))
    if missing:
        raise ValueError(f"missing fields: {','.join(missing)}")
    for field in ("event_id", "analysis_id", "upload_id"):
        uuid.UUID(str(event[field]))
    if not isinstance(event["user_id"], str) or not event["user_id"]:
        raise ValueError("user_id must be a non-empty string")
    if not isinstance(event["image_key"], str) or not event["image_key"]:
        raise ValueError("image_key must be a non-empty string")
    if event["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    return event


def validate_activity_event(event: Any) -> dict[str, Any]:
    """Validate a privacy-minimized backend-originated user activity event."""
    if not isinstance(event, dict):
        raise ValueError("activity event must be a JSON object")
    required = {"event_id", "event_type", "user_id", "occurred_at", "producer", "schema_version", "properties"}
    missing = sorted(required.difference(event))
    if missing:
        raise ValueError(f"missing fields:{','.join(missing)}")
    uuid.UUID(str(event["event_id"]))
    if not isinstance(event["user_id"], int) or event["user_id"] < 1:
        raise ValueError("user_id must be the positive PostgreSQL public.users.id")
    if not isinstance(event["event_type"], str) or not event["event_type"].startswith("user."):
        raise ValueError("event_type must start with user.")
    if not isinstance(event["producer"], str) or not event["producer"].endswith("-service"):
        raise ValueError("producer must be a service name")
    if event["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    if not isinstance(event["properties"], dict):
        raise ValueError("properties must be an object")
    try:
        datetime.fromisoformat(str(event["occurred_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("occurred_at must be ISO-8601") from exc
    return event


def completed_event(request: dict[str, Any], result: dict[str, Any], processor_version: str) -> dict[str, Any]:
    return {
        "event_id": str(uuid7()),
        "causation_event_id": request["event_id"],
        "analysis_id": request["analysis_id"],
        "upload_id": request["upload_id"],
        "user_id": request["user_id"],
        "result_ref": f"analysis:{request['analysis_id']}",
        "result": result,
        "processor_version": processor_version,
        "completed_at": utc_now(),
        "schema_version": SCHEMA_VERSION,
    }


def failed_event(request: dict[str, Any], error_code: str, attempts: int, retryable: bool = False) -> dict[str, Any]:
    return {
        "event_id": str(uuid7()),
        "causation_event_id": request.get("event_id"),
        "analysis_id": request.get("analysis_id"),
        "upload_id": request.get("upload_id"),
        "user_id": request.get("user_id"),
        "error_code": error_code,
        "attempt_count": attempts,
        "retryable": retryable,
        "failed_at": utc_now(),
        "schema_version": SCHEMA_VERSION,
    }
