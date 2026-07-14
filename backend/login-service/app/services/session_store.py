# Temporary in-memory holder for a single "active" test session token.
# Not a real session mechanism — only for local testing convenience.
_active_token: str | None = None


def set_active_token(token: str) -> None:
    global _active_token
    _active_token = token


def get_active_token() -> str | None:
    return _active_token
