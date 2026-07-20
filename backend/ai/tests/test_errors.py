from app.core.errors import ChatState


def test_chat_states_exist():
    assert ChatState.LOGIN_REQUIRED.value == "loginRequired"
    assert ChatState.IMG_ERROR.value == "imgError"
    assert ChatState.RETRY.value == "retry"
