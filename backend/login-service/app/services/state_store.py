import secrets
import time
from dataclasses import dataclass

# Temporary in-memory store until Redis is wired up; resets on every restart.
_STATE_TTL_SECONDS = 300


@dataclass
class StateEntry:
    expires_at: float
    link_user_id: int | None = None


_states: dict[str, StateEntry] = {}


def create_state(link_user_id: int | None = None) -> str:
    state = secrets.token_urlsafe(24)
    _states[state] = StateEntry(expires_at=time.time() + _STATE_TTL_SECONDS, link_user_id=link_user_id)
    return state


def verify_and_consume_state(state: str) -> StateEntry | None:
    entry = _states.pop(state, None)
    if entry is None or time.time() > entry.expires_at:
        return None
    return entry
