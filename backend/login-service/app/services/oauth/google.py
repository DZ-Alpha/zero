from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.oauth import OAUTH_HTTP_TIMEOUT
from app.services.oauth.types import NormalizedProfile, OAuthExchangeError

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def build_authorize_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "scope": "openid email profile",
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str, state: str) -> str:
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "code": code,
    }
    async with httpx.AsyncClient(timeout=OAUTH_HTTP_TIMEOUT) as client:
        response = await client.post(TOKEN_URL, data=data)
        response.raise_for_status()
        payload = response.json()

    if "access_token" not in payload:
        raise OAuthExchangeError(payload.get("error_description") or payload.get("error") or "구글 토큰 발급에 실패했습니다.")

    return payload["access_token"]


async def fetch_profile(access_token: str) -> NormalizedProfile:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=OAUTH_HTTP_TIMEOUT) as client:
        response = await client.get(USERINFO_URL, headers=headers)
        response.raise_for_status()
        payload = response.json()

    if "sub" not in payload:
        raise OAuthExchangeError(payload.get("error_description") or "구글 프로필 조회에 실패했습니다.")

    return NormalizedProfile(
        provider_user_id=payload["sub"],
        nickname=payload.get("name", ""),
        email=payload.get("email"),
        profile_image_url=payload.get("picture"),
        gender=None,
        birthday=None,
        birthyear=None,
    )
