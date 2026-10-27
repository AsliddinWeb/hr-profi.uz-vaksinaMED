import pytest

from tests.conftest import PASSWORD, login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)


async def test_login_success_sets_cookies_and_me(client):
    await make_user("ali", "hr_menejer")
    r = await login(client, "ali")
    assert r.status_code == 200
    body = r.json()
    assert body["login"] == "ali"
    assert body["role"]["key"] == "hr_menejer"
    assert "users.create" in body["permissions"]
    assert "vh_access" in r.headers.get("set-cookie", "")
    assert "HttpOnly" in r.headers.get("set-cookie", "")

    me = await client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["login"] == "ali"


async def test_login_is_case_insensitive_and_trims(client):
    await make_user("ali", "koordinator")
    assert (await login(client, "  ALI ")).status_code == 200


async def test_wrong_password_unknown_user_and_inactive_look_identical(client):
    await make_user("ali", "koordinator")
    await make_user("off", "koordinator", active=False)
    codes = set()
    for name, pwd in [("ali", "wrong-pass1"), ("nobody", PASSWORD), ("off", PASSWORD)]:
        r = await login(client, name, pwd)
        assert r.status_code == 401
        codes.add(r.json()["detail"]["code"])
    assert codes == {"invalid_credentials"}


async def test_rate_limit_after_five_failures(client):
    await make_user("ali", "koordinator")
    for _ in range(5):
        assert (await login(client, "ali", "bad-password1")).status_code == 401
    blocked = await login(client, "ali", PASSWORD)  # to'g'ri parol ham bloklanadi
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "too_many_attempts"


async def test_protected_endpoint_requires_auth(client):
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.get("/api/v1/users")).status_code == 401


async def test_csrf_header_required_for_mutations(app):
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post("/api/auth/login", json={"login": "a", "password": "b"})
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "csrf"


async def test_logout_revokes_session(client):
    await make_user("ali", "koordinator")
    await login(client, "ali")
    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_refresh_rotates_and_reuse_revokes_session(client, new_client):
    await make_user("ali", "koordinator")
    await login(client, "ali")
    old_refresh = client.cookies.get("vh_refresh", path="/api/auth")

    r = await client.post("/api/auth/refresh")
    assert r.status_code == 200
    new_refresh = client.cookies.get("vh_refresh", path="/api/auth")
    assert new_refresh != old_refresh

    # Eski tokenni ishlatish (o'g'irlik belgisi): sessiya yopiladi
    thief = new_client()
    thief.cookies.set("vh_refresh", old_refresh, path="/api/auth")
    assert (await thief.post("/api/auth/refresh")).status_code == 401
    # Haqiqiy foydalanuvchining sessiyasi ham yopilgan
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_must_change_password_flow(client):
    await make_user("ali", "hr_menejer", must_change=True)
    r = await login(client, "ali")
    assert r.json()["must_change_password"] is True

    assert (await client.get("/api/auth/me")).status_code == 200
    blocked = await client.get("/api/v1/users")
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "password_change_required"

    weak = await client.post(
        "/api/auth/change-password", json={"old_password": PASSWORD, "new_password": "12345678"}
    )
    assert weak.json()["detail"]["code"] == "password_too_simple"
    wrong = await client.post(
        "/api/auth/change-password", json={"old_password": "nope-nope1", "new_password": "Better-pass1"}
    )
    assert wrong.json()["detail"]["code"] == "wrong_old_password"

    ok = await client.post(
        "/api/auth/change-password", json={"old_password": PASSWORD, "new_password": "Better-pass1"}
    )
    assert ok.status_code == 204
    assert (await client.get("/api/v1/users")).status_code == 200


async def test_change_password_revokes_other_sessions(client, new_client):
    await make_user("ali", "koordinator")
    await login(client, "ali")
    other = new_client()
    await login(other, "ali")
    await client.post(
        "/api/auth/change-password", json={"old_password": PASSWORD, "new_password": "Better-pass1"}
    )
    assert (await client.get("/api/auth/me")).status_code == 200
    assert (await other.get("/api/auth/me")).status_code == 401


async def test_my_sessions_list_and_revoke(client, new_client):
    await make_user("ali", "koordinator")
    await login(client, "ali")
    other = new_client()
    await login(other, "ali")
    sessions = (await client.get("/api/auth/sessions")).json()
    assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1
    victim = next(s for s in sessions if not s["current"])
    assert (await client.delete(f"/api/auth/sessions/{victim['id']}")).status_code == 204
    assert (await other.get("/api/auth/me")).status_code == 401


async def test_profile_update(client):
    await make_user("ali", "koordinator")
    await login(client, "ali")
    r = await client.patch("/api/auth/me", json={"locale": "ru", "phone": "+998901112233"})
    assert r.json()["locale"] == "ru" and r.json()["phone"] == "+998901112233"
    assert (await client.patch("/api/auth/me", json={"locale": "en"})).status_code == 422
