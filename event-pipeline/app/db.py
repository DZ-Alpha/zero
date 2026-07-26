from __future__ import annotations

import json
import threading
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import Settings


SCHEMA_FILE = Path(__file__).resolve().parent.parent / "sql" / "001_pipeline.sql"

_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool(settings: Settings) -> ConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ConnectionPool(
                    settings.database_url,
                    min_size=settings.db_pool_min_size,
                    max_size=settings.db_pool_max_size,
                    timeout=settings.db_pool_timeout_seconds,
                    kwargs={"row_factory": dict_row},
                    name="dangdang-pipeline",
                    open=True,
                )
    return _pool


def connect(settings: Settings) -> AbstractContextManager[psycopg.Connection]:
    """Borrow a pooled connection for one transaction.

    The returned context manager keeps the previous semantics: the block
    commits on a clean exit and rolls back on an exception. The only change is
    that the connection returns to the pool instead of being closed, so the
    per-job TCP setup disappears once several workers run in parallel.
    """
    return _get_pool(settings).connection()


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None


def initialize(settings: Settings) -> None:
    with connect(settings) as conn:
        conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))


def json_value(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

