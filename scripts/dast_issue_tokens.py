#!/usr/bin/env python3
"""
DAST staging 인증 토큰 발급기.

무엇: staging에 시딩된 가짜 유저로 JWT를 발급한다. active scan에 Bearer로 주입해
    인증된 상태의 IDOR/권한 검증을 수행하기 위함.

IDOR 쌍: 시더가 만든 user_id=1(방0 멤버)과 user_id=4(방0 비멤버) 두 토큰을 발급한다.
    → 스캔에서 "1의 토큰으로 4의 리소스 접근" 또는 "4의 토큰으로 1이 속한 방 접근"을
      시도해 접근제어가 막는지 검증한다.

⚠️ 보안 메모(발견된 취약점): staging과 운영(prod)의 JWT_SECRET이 동일하다
    (2026-07-30 확인, 양쪽 dang-jwt-secret SealedSecret 값이 바이트 단위로 일치).
    → 여기서 발급하는 토큰은 운영에도 통한다. 그래서:
      - 만료를 짧게(기본 3h) 두고 스캔에만 쓰고 버린다. 1년 토큰 금지.
      - 이 secret 공유 자체는 실증 리포트에 "취약점: staging/prod JWT 미격리"로
        기록하고 담당자에게 secret 분리를 요청한다(운영 secret 구조 변경은 월권).

서명: HS256, jwt_service.create_access_token과 동일 payload(sub/user_id/provider/
    nickname/role/iat/exp). secret은 env JWT_SECRET에서 로드(하드코딩 금지).

실행: JWT_SECRET=... python scripts/dast_issue_tokens.py
    (staging login-service의 실제 JWT_SECRET을 넘긴다. 파드 exec 또는 임시 파드에서)
    출력: user_id별 Bearer 토큰. 스캔 러너(Task9)가 이 값을 replacer로 주입.
"""
import json
import os
import time

import jwt

# IDOR 쌍 (시더 기준: 방0 멤버=1, 방0 비멤버=4). 필요시 env로 override.
USER_IDS = [int(x) for x in os.getenv("DAST_USER_IDS", "1,4").split(",")]
EXPIRE_SECONDS = int(os.getenv("DAST_TOKEN_TTL", str(3 * 3600)))  # 기본 3h — 스캔용, 짧게


def issue(user_id: int, secret: str, role: str = "user") -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "user_id": user_id,          # 다른 서비스가 payload["user_id"]를 읽음
        "provider": "dast-seed",
        "nickname": f"dast{user_id}",
        "role": role,
        "iat": now,
        "exp": now + EXPIRE_SECONDS,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def main() -> None:
    secret = os.environ["JWT_SECRET"]           # 필수 — 하드코딩 금지
    tokens = {uid: issue(uid, secret) for uid in USER_IDS}
    # 스캔 러너가 파싱하기 쉽게 JSON으로도 출력.
    for uid, tok in tokens.items():
        print(f"user_id={uid}: {tok}")
    print("JSON:", json.dumps({str(uid): tok for uid, tok in tokens.items()}))
    print(f"(만료 {EXPIRE_SECONDS // 3600}h — 스캔에만 쓰고 버릴 것. 1년 토큰 금지: prod와 secret 공유)")


if __name__ == "__main__":
    main()
