from datetime import datetime, timezone, timedelta
import redis
from kafka.config import REDIS_URL, CURSOR_KEY

INITIAL_LOOKBACK_HOURS = 24


def _client():
    return redis.from_url(REDIS_URL, decode_responses=True)


def read_cursor() -> datetime:
    raw = _client().get(CURSOR_KEY)
    if raw:
        return datetime.fromisoformat(raw)
    return datetime.now(timezone.utc) - timedelta(hours=INITIAL_LOOKBACK_HOURS)


def write_cursor(dt: datetime) -> None:
    _client().set(CURSOR_KEY, dt.isoformat())
