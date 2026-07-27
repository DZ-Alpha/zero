import time

import httpx
import jwt
import pytest

from app.context.backend import BackendUserContextProvider
from app.core.config import settings


def _token():
    now = int(time.time())
    return jwt.encode({"sub": "1", "nickname": "t", "iat": now, "exp": now + 3600},
                      settings.jwt_secret, algorithm="HS256")


def _handler(mypage: dict, profile: dict, diet: dict | None):
    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/user/mypage"):
            return httpx.Response(200, json=mypage)
        if path.endswith("/home/health-profile"):
            return httpx.Response(200, json=profile)
        if path.endswith("/home/user-sugar-calorie"):
            if diet is None:
                return httpx.Response(500, json={})
            return httpx.Response(200, json=diet)
        return httpx.Response(404)
    return handler


def _provider(handler):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return BackendUserContextProvider(
        login_url="http://login", main_url="http://main",
        diet_url="http://diet", http_client=client)


async def test_today_intake_loaded():
    p = _provider(_handler(
        mypage={"favorite": [], "healthStat": {}},
        profile={"consent": True, "dailySugarTargetG": 50, "dailyCalorieTarget": 2000},
        diet={"sugar": 25, "cal": 750, "sugar_target": 50, "cal_target": 2000}))
    ctx = await p.load(_token())
    assert ctx.today_sugar == 25
    assert ctx.today_cal == 750


async def test_diet_failure_isolated():
    # diet만 실패해도 mypage/profile은 정상, today_*만 None
    p = _provider(_handler(
        mypage={"favorite": ["저당"], "healthStat": {}},
        profile={"consent": True, "dailySugarTargetG": 50, "dailyCalorieTarget": 2000},
        diet=None))  # 500
    ctx = await p.load(_token())
    assert ctx.today_sugar is None
    assert ctx.today_cal is None
    assert ctx.interests == ["저당"]        # mypage 정상
    assert ctx.daily_sugar_target_g == 50   # profile 정상
