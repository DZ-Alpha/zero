_PREFIX = "chat:history:"


def resolve_session_key(user_id: int | None, session_id: str | None) -> str | None:
    """대화방 세션키를 결정한다. 로그인(user_id>0)이면 계정 기준,
    아니면 프론트가 준 session_id로 게스트 기준. 둘 다 없으면 None(단발)."""
    if user_id:
        return f"{_PREFIX}user:{user_id}"
    if session_id:
        return f"{_PREFIX}guest:{session_id}"
    return None
