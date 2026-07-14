from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.oauth.types import NormalizedProfile, OAuthExchangeError

AUTHORIZE_URL = "https://nid.naver.com/oauth2.0/authorize"
TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
USERINFO_URL = "https://openapi.naver.com/v1/nid/me"


def build_authorize_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.naver_client_id,
        "redirect_uri": settings.naver_redirect_uri,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str, state: str) -> str:
    params = {
        "grant_type": "authorization_code",
        "client_id": settings.naver_client_id,
        "client_secret": settings.naver_client_secret,
        "code": code,
        "state": state,
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(TOKEN_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    if "access_token" not in payload:
        raise OAuthExchangeError(payload.get("error_description") or payload.get("error") or "네이버 토큰 발급에 실패했습니다.")

    return payload["access_token"]


async def fetch_profile(access_token: str) -> NormalizedProfile:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(USERINFO_URL, headers=headers)
        response.raise_for_status()
        body = response.json()

    if "response" not in body:
        raise OAuthExchangeError(body.get("message") or "네이버 프로필 조회에 실패했습니다.")

    payload = body["response"]

    return NormalizedProfile(
        provider_user_id=payload["id"],
        nickname=payload.get("nickname", ""),
        email=payload.get("email"),
        profile_image_url=payload.get("profile_image"),
        gender=payload.get("gender"),
        birthday=payload.get("birthday"),
        birthyear=payload.get("birthyear"),
    )
