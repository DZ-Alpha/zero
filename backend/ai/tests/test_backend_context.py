from datetime import datetime, timezone

import httpx

from app.context.backend import BackendUserContextProvider


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/user/mypage":
        return httpx.Response(200, json={
            "enabledSns": ["GL"], "email": "a@b.c", "optionalAgree": True,
            "favorite": ["저당", "고단백"],
            # 몸무게가 health-profile과 일부러 다르다(옛날/갱신 시점 차이 모사).
            # 목표 계산은 health-profile 값을 써야 하므로 이 99는 무시돼야 한다.
            "healthStat": {"optionalAgree": True, "allergic": True, "tall": 999, "weight": 99.0, "age": 99},
        })
    if request.url.path == "/home/health-profile":
        return httpx.Response(200, json={
            "birthYear": 2000, "gender": "여성", "heightCm": 165.0, "weightKg": 55.0,
            "activityLevel": "가벼운 운동을 주 1~3회 해요", "healthGoal": "BALANCE",
            "dailyCalorieTarget": 1900.0, "dailySugarTargetG": 48.0,
            "targetSource": "USER", "consent": True,
        })
    return httpx.Response(404)


async def test_backend_provider_assembles_context():
    client = httpx.AsyncClient(transport=httpx.MockTransport(_handler))
    provider = BackendUserContextProvider(login_url="http://login", main_url="http://main", http_client=client)
    ctx = await provider.load("some-token")
    assert ctx.logged_in is True
    assert ctx.interests == ["저당", "고단백"]
    assert ctx.has_allergy is True
    assert ctx.consent is True
    assert ctx.daily_sugar_target_g == 48.0
    assert ctx.daily_calorie_target == 1900.0
    # 신체정보는 health-profile에서 읽는다(mypage의 99/999가 아니라).
    assert ctx.weight_kg == 55.0
    assert ctx.height_cm == 165.0
    assert ctx.gender == "여성"
    assert ctx.activity_level == "가벼운 운동을 주 1~3회 해요"
    assert ctx.age == datetime.now(timezone.utc).year - 2000


async def test_backend_provider_401_falls_back_to_anonymous():
    def deny(request): return httpx.Response(401, json={"detail": "무효"})
    client = httpx.AsyncClient(transport=httpx.MockTransport(deny))
    provider = BackendUserContextProvider(login_url="http://login", main_url="http://main", http_client=client)
    ctx = await provider.load("bad")
    assert ctx.logged_in is False
