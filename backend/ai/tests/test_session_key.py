from app.memory.session_key import resolve_session_key


def test_logged_in_user_key():
    assert resolve_session_key(user_id=42, session_id=None) == "chat:history:user:42"


def test_logged_in_ignores_session_id():
    assert resolve_session_key(user_id=42, session_id="abc") == "chat:history:user:42"


def test_guest_key():
    assert resolve_session_key(user_id=None, session_id="abc-123") == "chat:history:guest:abc-123"


def test_anonymous_user_id_zero_treated_as_guest():
    # 익명 컨텍스트는 user_id=0 — 로그인 아님
    assert resolve_session_key(user_id=0, session_id="abc") == "chat:history:guest:abc"


def test_no_identity_returns_none():
    assert resolve_session_key(user_id=None, session_id=None) is None
    assert resolve_session_key(user_id=0, session_id=None) is None
