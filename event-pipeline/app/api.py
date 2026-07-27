from __future__ import annotations

import hashlib
import logging
from contextlib import asynccontextmanager
from urllib.parse import unquote, urlparse

from fastapi import Body, FastAPI, Header, HTTPException, Query, Response, status
from minio import Minio

from app.config import load_settings
from app.contracts import requested_event, uuid7
from app.db import close_pool, connect, initialize, json_value
from app.outbox import OutboxPublisher


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
settings = load_settings()
minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure,
)
publisher = OutboxPublisher(settings)


def user_key(token: str) -> str:
    if not token or len(token) > 8192:
        raise HTTPException(status_code=401, detail="invalid user token")
    return "usr:" + hashlib.sha256(token.encode()).hexdigest()


def image_key_from_ref(source_ref: str) -> str:
    if not source_ref or len(source_ref) > 2048:
        raise HTTPException(status_code=422, detail="invalid img")
    parsed = urlparse(source_ref)
    if parsed.scheme == "minio":
        if parsed.netloc != settings.minio_bucket:
            raise HTTPException(status_code=422, detail="img must reference the diet-photos bucket")
        key = unquote(parsed.path.lstrip("/"))
    elif parsed.scheme in {"http", "https"}:
        public = urlparse(settings.minio_public_endpoint)
        allowed_hosts = {public.netloc, settings.minio_endpoint}
        if parsed.netloc not in allowed_hosts:
            raise HTTPException(status_code=422, detail="img host is not the local MinIO endpoint")
        prefix = f"/{settings.minio_bucket}/"
        if not parsed.path.startswith(prefix):
            raise HTTPException(status_code=422, detail="img must reference the diet-photos bucket")
        key = unquote(parsed.path[len(prefix) :])
    elif not parsed.scheme:
        key = source_ref.lstrip("/")
    else:
        raise HTTPException(status_code=422, detail="unsupported img scheme")
    if not key or ".." in key.split("/") or any(ch.isspace() for ch in key):
        raise HTTPException(status_code=422, detail="invalid MinIO object key")
    return key


def get_owned_job(analysis_id: str, owner: str) -> dict:
    with connect(settings) as conn:
        row = conn.execute(
            """
            SELECT analysis_id, upload_id, status, attempt_count, result,
                   failure_code, created_at, updated_at
            FROM diet_analysis_jobs
            WHERE analysis_id=%s AND user_id=%s
            """,
            (analysis_id, owner),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return row


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize(settings)
    if not minio_client.bucket_exists(settings.minio_bucket):
        raise RuntimeError(f"required MinIO bucket does not exist: {settings.minio_bucket}")
    publisher.start()
    yield
    publisher.stop()
    publisher.join(timeout=12)
    close_pool()


app = FastAPI(title="DangDang Diet Event Pipeline", version="1.0.0", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    with connect(settings) as conn:
        conn.execute("SELECT 1").fetchone()
    minio_client.bucket_exists(settings.minio_bucket)
    return {"status": "ok"}


@app.post("/b/diet/upload")
def upload_diet(body: dict = Body(...), usr: str = Query(..., min_length=1)) -> dict[str, str]:
    source_ref = body.get("img")
    if not isinstance(source_ref, str):
        raise HTTPException(status_code=422, detail="required field: img")
    mode = body.get("mode")
    if mode not in {None, "daily"}:
        raise HTTPException(status_code=422, detail="mode must be daily when provided")
    key = image_key_from_ref(source_ref)
    try:
        minio_client.stat_object(settings.minio_bucket, key)
    except Exception as exc:
        logger.info("upload reference not found key=%s", key)
        raise HTTPException(status_code=422, detail="img object does not exist") from exc

    owner = user_key(usr)
    upload_id = uuid7()
    with connect(settings) as conn:
        row = conn.execute(
            """
            INSERT INTO diet_uploads (upload_id, user_id, source_ref, image_key, mode)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, source_ref) DO UPDATE
            SET deleted_at=NULL, image_key=EXCLUDED.image_key, mode=EXCLUDED.mode
            RETURNING upload_id
            """,
            (upload_id, owner, source_ref, key, mode),
        ).fetchone()
    return {"status": "SUCCESS", "id": str(row["upload_id"])}


@app.post("/b/diet/ai-analyze", status_code=status.HTTP_202_ACCEPTED)
def request_analysis(body: dict = Body(...), usr: str = Query(..., min_length=1)) -> dict[str, str]:
    source_ref = body.get("img")
    if not isinstance(source_ref, str):
        raise HTTPException(status_code=422, detail="required field: img")
    owner = user_key(usr)
    with connect(settings) as conn:
        upload = conn.execute(
            """
            SELECT upload_id, image_key FROM diet_uploads
            WHERE user_id=%s AND source_ref=%s AND deleted_at IS NULL
            """,
            (owner, source_ref),
        ).fetchone()
        if upload is None:
            raise HTTPException(status_code=404, detail="registered upload not found")
        existing = conn.execute(
            "SELECT analysis_id, status FROM diet_analysis_jobs WHERE upload_id=%s",
            (upload["upload_id"],),
        ).fetchone()
        if existing is not None:
            return {"id": str(existing["analysis_id"]), "status": existing["status"]}

        analysis_id = uuid7()
        event_id = uuid7()
        event = requested_event(
            event_id=event_id,
            analysis_id=analysis_id,
            upload_id=upload["upload_id"],
            user_id=owner,
            image_key=upload["image_key"],
        )
        conn.execute(
            """
            INSERT INTO diet_analysis_jobs
                (analysis_id, request_event_id, upload_id, user_id, status)
            VALUES (%s, %s, %s, %s, 'PENDING')
            """,
            (analysis_id, event_id, upload["upload_id"], owner),
        )
        conn.execute(
            """
            INSERT INTO outbox_events
                (event_id, causation_event_id, topic, event_key, payload)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (event_id, event_id, settings.request_topic, owner, json_value(event)),
        )
    return {"id": str(analysis_id), "status": "PENDING"}


@app.get("/b/diet/ai-analyze")
def analysis_result(response: Response, id: str = Query(...), usr: str = Query(..., min_length=1)) -> dict:
    row = get_owned_job(id, user_key(usr))
    if row["status"] in {"PENDING", "PROCESSING"}:
        response.status_code = status.HTTP_202_ACCEPTED
        return {"id": str(row["analysis_id"]), "status": row["status"]}
    if row["status"] == "FAILED":
        return {
            "id": str(row["analysis_id"]),
            "status": "FAILED",
            "error": row["failure_code"] or "ANALYSIS_FAILED",
        }
    result = row["result"] or {}
    return {
        "id": str(row["analysis_id"]),
        "status": "DONE",
        "list-diet": result.get("list-diet", []),
        "confidence": result.get("confidence"),
        "confidence_source": result.get("confidence_source"),
        "needs_user_confirmation": bool(result.get("needs_user_confirmation")),
    }


@app.get("/b/diet/other-foods")
def other_foods(id: str = Query(...), usr: str = Query(..., min_length=1)) -> dict:
    row = get_owned_job(id, user_key(usr))
    if row["status"] != "DONE":
        raise HTTPException(status_code=409, detail="analysis is not complete")
    items = (row["result"] or {}).get("list-diet", [])
    return {
        "id": str(row["analysis_id"]),
        "dang": sum(float(item.get("dang") or 0) for item in items),
        "calo": sum(float(item.get("calo") or 0) for item in items),
        "list-diet": items,
    }


@app.delete("/b/diet/upload/{upload_id}")
def delete_upload(upload_id: str, authorization: str | None = Header(default=None)) -> dict[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    owner = user_key(authorization[7:])
    with connect(settings) as conn:
        upload = conn.execute(
            "SELECT upload_id, image_key FROM diet_uploads WHERE upload_id=%s AND user_id=%s AND deleted_at IS NULL",
            (upload_id, owner),
        ).fetchone()
        if upload is None:
            raise HTTPException(status_code=404, detail="upload not found")
        active = conn.execute(
            "SELECT 1 FROM diet_analysis_jobs WHERE upload_id=%s AND status IN ('PENDING','PROCESSING')",
            (upload_id,),
        ).fetchone()
        if active is not None:
            raise HTTPException(status_code=409, detail="analysis is active")
        minio_client.remove_object(settings.minio_bucket, upload["image_key"])
        conn.execute("UPDATE diet_uploads SET deleted_at=now() WHERE upload_id=%s", (upload_id,))
    return {"status": "SUCCESS"}
