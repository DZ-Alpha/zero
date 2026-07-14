from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.oauth.types import NormalizedProfile, OAuthExchangeError

AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
USERINFO_URL = "https://kapi.kakao.com/v2/user/me"


def build_authorize_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.kakao_client_id,
        "redirect_uri": settings.kakao_redirect_uri,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str, state: str) -> str:
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.kakao_client_id,
        "redirect_uri": settings.kakao_redirect_uri,
        "code": code,
    }
    if settings.kakao_client_secret:
        data["client_secret"] = settings.kakao_client_secret

    async with httpx.AsyncClient() as client:
        response = await client.post(TOKEN_URL, data=data)
        response.raise_for_status()
        payload = response.json()

    if "access_token" not in payload:
        raise OAuthExchangeError(payload.get("error_description") or payload.get("error") or "카카오 토큰 발급에 실패했습니다.")

    return payload["access_token"]


async def fetch_profile(access_token: str) -> NormalizedProfile:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(USERINFO_URL, headers=headers)
        response.raise_for_status()
        payload = response.json()

    if "id" not in payload:
        raise OAuthExchangeError(payload.get("msg") or "카카오 프로필 조회에 실패했습니다.")

    kakao_account = payload.get("kakao_account", {})
    profile = kakao_account.get("profile", {})

    return NormalizedProfile(
        provider_user_id=str(payload["id"]),
        nickname=profile.get("nickname", ""),
        email=kakao_account.get("email"),
        profile_image_url=profile.get("profile_image_url"),
        gender=kakao_account.get("gender"),
        birthday=kakao_account.get("birthday"),
        birthyear=kakao_account.get("birthyear"),
    )
