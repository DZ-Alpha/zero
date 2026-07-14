from dataclasses import dataclass


@dataclass
class NormalizedProfile:
    provider_user_id: str
    nickname: str
    email: str | None
    profile_image_url: str | None
    gender: str | None
    birthday: str | None
    birthyear: str | None


class OAuthExchangeError(Exception):
    pass
