import pytest

from tests.conftest import PASSWORD, login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")


def _login(c, name, key):
    return c.post("/api/auth/login", json={"login": name, "password": PASSWORD}, headers={"X-Device-Id": key})


async def test_devices_enforced_flow(new_client):
    await make_user("hrdev", "hr_direktor")
    fid = await make_user("farmdev", "farmasevt")
    hr = new_client()
    assert (await login(hr, "hrdev")).status_code == 200
    # nazorat yoqilmagan: istalgan qurilmadan kiradi, qurilma qayd etiladi
    a = new_client()
    assert (await _login(a, "farmdev", "phone-AAAAAAAA")).status_code == 200
    s = await hr.put("/api/v1/devices/settings", json={"enforce_roles": [], "enforce_user_ids": [fid], "auto_approve_first": True})
    assert s.status_code == 200, s.text
    # birinchi (asosiy) qurilma tasdiqlangan
    assert (await _login(new_client(), "farmdev", "phone-AAAAAAAA")).status_code == 200
    # yangi qurilma -> ruxsat so'rovi
    r = await _login(new_client(), "farmdev", "laptop-BBBBBBBB")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "device_pending"
    assert (await _login(new_client(), "farmdev", "")).json()["detail"]["code"] == "device_unknown"
    pend = (await hr.get("/api/v1/devices", params={"status": "pending"})).json()
    assert pend["total"] == 1
    did = pend["items"][0]["id"]
    assert (await hr.get("/api/v1/devices/summary")).json()["pending"] == 1
    ok = await hr.post(f"/api/v1/devices/{did}/approve")
    assert ok.json()["status"] == "approved" and ok.json()["is_primary"]
    assert (await _login(new_client(), "farmdev", "laptop-BBBBBBBB")).status_code == 200
    await hr.post(f"/api/v1/devices/{did}/block")
    assert (await _login(new_client(), "farmdev", "laptop-BBBBBBBB")).json()["detail"]["code"] == "device_blocked"
    sec = (await hr.get("/api/v1/devices/logins", params={"security": "true"})).json()
    assert {i["action"] for i in sec["items"]} >= {"device_pending", "device_blocked", "device_unknown"}
    # oddiy xodim ko'ra olmaydi
    assert (await a.get("/api/v1/devices")).status_code in (401, 403)
