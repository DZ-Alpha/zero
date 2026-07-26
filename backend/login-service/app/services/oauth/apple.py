import time
from urllib.parse import urlencode

import httpx
import jwt as pyjwt

from app.core.config import settings
from app.services.oauth.types import NormalizedProfile, OAuthExchangeError

AUTHORIZE_URL = "https://appleid.apple.com/auth/authorize"
TOKEN_URL = "https://appleid.apple.com/auth/token"
JWKS_URL = "https://appleid.apple.com/auth/keys"

_jwks_client = pyjwt.PyJWKClient(JWKS_URL)


def build_authorize_url(state: str) -> str:
    # No `scope` requested on purpose: Apple only returns name/email once
    # (first authorization) and forces response_mode=form_post whenever any
    # scope is requested, which needs a POST callback route — this app's
    # /social-access/{provider}/callback is GET-only. 이메일은 가입 단계에서
    # 별도로 필수 입력받으니(SignupProfileForm.tsx) scope 없이 간다.
    params = {
        "response_type": "code",
        "response_mode": "query",
        "client_id": settings.apple_client_id,
        "redirect_uri": settings.apple_redirect_uri,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _build_client_secret() -> str:
    """Apple은 고정 client_secret이 아니라, Team ID/Key ID/private key(.p8)로
    매 요청 서명하는 JWT(ES256)를 요구한다 — 최대 6개월 만료가 규칙이라
    여유있게 5분짜리로 그때그때 새로 만든다."""
    now = int(time.time())
    return pyjwt.encode(
        {
            "iss": settings.apple_team_id,
            "iat": now,
            "exp": now + 300,
            "aud": "https://appleid.apple.com",
            "sub": settings.apple_client_id,
        },
        settings.apple_private_key_pem,
        algorithm="ES256",
        headers={"kid": settings.apple_key_id},
    )


async def exchange_code_for_token(code: str, state: str) -> str:
    data = {
        "client_id": settings.apple_client_id,
        "client_secret": _build_client_secret(),
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.apple_redirect_uri,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(TOKEN_URL, data=data)
        payload = response.json()

    if "id_token" not in payload:
        raise OAuthExchangeError(payload.get("error_description") or payload.get("error") or "Apple 토큰 발급에 실패했습니다.")

    # 반환값은 access_token이 아니라 id_token이다 — Apple은 별도 프로필 조회
    # API가 없고, 필요한 정보(sub)가 전부 id_token 안에 들어있다.
    return payload["id_token"]


async def fetch_profile(access_token: str) -> NormalizedProfile:
    id_token = access_token
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(id_token)
        claims = pyjwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.apple_client_id,
            issuer="https://appleid.apple.com",
        )
    except pyjwt.InvalidTokenError as error:
        raise OAuthExchangeError(f"Apple id_token 검증에 실패했습니다: {error}") from error

    # scope 없이 요청해서 name/email은 안 내려온다 - 가입 단계에서 이메일을
    # 별도로 받는다(get_or_create_user가 email=None을 그대로 받아들인다).
    return NormalizedProfile(
        provider_user_id=claims["sub"],
        nickname="",
        email=claims.get("email"),
        profile_image_url=None,
        gender=None,
        birthday=None,
        birthyear=None,
    )
