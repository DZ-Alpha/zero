from enum import Enum


class ChatState(str, Enum):
    """프론트 MN-0114 상태값과 1:1 매핑."""
    LOADING = "loading"
    EMPTY = "empty"
    ERROR = "error"
    RETRY = "retry"
    IMG_ERROR = "imgError"
    LOGIN_REQUIRED = "loginRequired"
