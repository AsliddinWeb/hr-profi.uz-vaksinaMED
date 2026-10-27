import pytest

from tests.conftest import PASSWORD, login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)


async def as_user(new_client, login_name: str, role: str, **kw):
    await make_user(login_name, role, **kw)
    c = new_client()
    r = await login(c, login_name)
    assert r.status_code == 200
    return c


async def test_user_without_permission_is_forbidden(new_client):
    c = await as_user(new_client, "kor", "koordinator")
    r = await c.get("/api/v1/users")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden"


async def test_create_user_generates_login_and_temp_password(new_client):
    hr = await as_user(new_client, "hr", "hr_menejer")
    r = await hr.post(
        "/api/v1/users", json={"full_name": "Tursunboyev Orifjon", "role_key": "koordinator"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["login"] == "tursunboyev.orifjon"
    assert body["user"]["must_change_password"] is True
    temp = body["temp_password"]
    assert temp and len(temp) >= 10

    # Bir xil ism: login takrorlanmaydi
    r2 = await hr.post(
        "/api/v1/users", json={"full_name": "Tursunboyev Orifjon", "role_key": "koordinator"}
    )
    assert r2.json()["user"]["login"] == "tursunboyev.orifjon2"

    # Yangi foydalanuvchi vaqtinchalik parol bilan kira oladi
    newbie = new_client()
    rl = await login(newbie, "tursunboyev.orifjon", temp)
    assert rl.status_code == 200 and rl.json()["must_change_password"] is True


async def test_cyrillic_name_is_transliterated(new_client):
    hr = await as_user(new_client, "hr", "hr_menejer")
    r = await hr.post("/api/v1/users", json={"full_name": "Собиров Асадбек", "role_key": "mudir"})
    assert r.json()["user"]["login"] == "sobirov.asadbek"


async def test_cannot_assign_role_with_more_permissions(new_client):
    hr = await as_user(new_client, "hr", "hr_menejer")
    for role in ("tasischi", "hr_direktor", "direktor"):  # direktor: audit.read, hr_menejer'da yo'q
        r = await hr.post("/api/v1/users", json={"full_name": "Test User", "role_key": role})
        assert r.status_code == 403, role
        assert r.json()["detail"]["code"] == "cannot_assign_role"
    ok = await hr.post("/api/v1/users", json={"full_name": "Test User", "role_key": "stajyor"})
    assert ok.status_code == 201


async def test_cannot_manage_higher_user(new_client):
    boss_id = await make_user("boss", "hr_direktor")
    hr = await as_user(new_client, "hr", "hr_menejer")
    for path in (f"/api/v1/users/{boss_id}/reset-password",):
        r = await hr.post(path)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "cannot_manage_user"
    r = await hr.patch(f"/api/v1/users/{boss_id}", json={"full_name": "Hacked Name"})
    assert r.status_code == 403


async def test_deactivate_revokes_sessions_and_blocks_login(new_client):
    boss = await as_user(new_client, "boss", "hr_direktor")
    victim_id = await make_user("vic", "koordinator")
    vic = new_client()
    await login(vic, "vic")

    r = await boss.post(f"/api/v1/users/{victim_id}/deactivate")
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (await vic.get("/api/auth/me")).status_code == 401
    assert (await login(new_client(), "vic")).status_code == 401

    assert (await boss.post(f"/api/v1/users/{victim_id}/activate")).json()["is_active"] is True
    assert (await login(new_client(), "vic")).status_code == 200


async def test_cannot_deactivate_self_or_last_superuser(new_client):
    root = await as_user(new_client, "root", "tasischi")
    me = (await root.get("/api/auth/me")).json()["id"]
    r = await root.post(f"/api/v1/users/{me}/deactivate")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "cannot_deactivate_self"

    # Ikkinchi ta'sischi bor bo'lsa, birinchisini o'chirish mumkin; oxirgisini yo'q
    other_id = await make_user("root2", "tasischi")
    assert (await root.post(f"/api/v1/users/{other_id}/deactivate")).status_code == 200
    root2_again = await root.post(f"/api/v1/users/{other_id}/activate")
    assert root2_again.status_code == 200


async def test_last_superuser_cannot_be_demoted(new_client):
    root = await as_user(new_client, "root", "tasischi")
    me = (await root.get("/api/auth/me")).json()["id"]
    r = await root.patch(f"/api/v1/users/{me}", json={"role_key": "direktor"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "last_superuser"


async def test_reset_password_forces_change_and_kills_sessions(new_client):
    boss = await as_user(new_client, "boss", "hr_direktor")
    vid = await make_user("vic", "koordinator")
    vic = new_client()
    await login(vic, "vic")
    r = await boss.post(f"/api/v1/users/{vid}/reset-password")
    temp = r.json()["temp_password"]
    assert (await vic.get("/api/auth/me")).status_code == 401
    again = await login(new_client(), "vic", temp)
    assert again.status_code == 200 and again.json()["must_change_password"] is True
    assert (await login(new_client(), "vic", PASSWORD)).status_code == 401


async def test_role_change_revokes_target_sessions(new_client):
    boss = await as_user(new_client, "boss", "hr_direktor")
    vid = await make_user("vic", "koordinator")
    vic = new_client()
    await login(vic, "vic")
    r = await boss.patch(f"/api/v1/users/{vid}", json={"role_key": "mudir"})
    assert r.status_code == 200 and r.json()["role_key"] == "mudir"
    assert (await vic.get("/api/auth/me")).status_code == 401


async def test_list_users_search_and_pagination(new_client):
    hr = await as_user(new_client, "hr", "hr_menejer")
    for i in range(5):
        await make_user(f"u{i}", "farmasevt", name=f"Farm {i}")
    r = await hr.get("/api/v1/users", params={"role": "farmasevt", "size": 2, "page": 2})
    body = r.json()
    assert body["total"] == 5 and len(body["items"]) == 2
    r = await hr.get("/api/v1/users", params={"q": "farm 3"})
    assert [u["login"] for u in r.json()["items"]] == ["u3"]


async def test_roles_listing_and_permission_edit(new_client):
    boss = await as_user(new_client, "boss", "hr_direktor")
    roles = (await boss.get("/api/v1/roles")).json()
    assert {r["key"] for r in roles} >= {"tasischi", "koordinator", "resepshin", "ayti"}
    kor = next(r for r in roles if r["key"] == "koordinator")

    r = await boss.put(
        f"/api/v1/roles/{kor['id']}/permissions", json={"permissions": ["users.read"]}
    )
    assert r.status_code == 200 and r.json()["permissions"] == ["users.read"]
    # Qayta yozish (bir xil kalit bilan) ham xatosiz
    r = await boss.put(
        f"/api/v1/roles/{kor['id']}/permissions", json={"permissions": ["users.read", "audit.read"]}
    )
    assert r.json()["permissions"] == ["audit.read", "users.read"]

    # Koordinator endi foydalanuvchilarni ko'ra oladi
    await make_user("kor", "koordinator")
    c = new_client()
    await login(c, "kor")
    assert (await c.get("/api/v1/users")).status_code == 200


async def test_role_edit_guards(new_client):
    boss = await as_user(new_client, "boss", "hr_direktor")
    roles = {r["key"]: r for r in (await boss.get("/api/v1/roles")).json()}

    locked = await boss.put(
        f"/api/v1/roles/{roles['tasischi']['id']}/permissions", json={"permissions": ["users.read"]}
    )
    assert locked.status_code == 409 and locked.json()["detail"]["code"] == "role_locked"

    unknown = await boss.put(
        f"/api/v1/roles/{roles['mudir']['id']}/permissions", json={"permissions": ["nope.nothing"]}
    )
    assert unknown.status_code == 400

    # '*' ni faqat '*' egasi bera oladi
    star = await boss.put(
        f"/api/v1/roles/{roles['mudir']['id']}/permissions", json={"permissions": ["*"]}
    )
    assert star.status_code == 403 and star.json()["detail"]["code"] == "cannot_grant_permission"


async def test_audit_log_records_actions_and_hides_secrets(new_client):
    boss = await as_user(new_client, "boss", "hr_direktor")
    await boss.post("/api/v1/users", json={"full_name": "Audit Test", "role_key": "stajyor"})
    r = await boss.get("/api/v1/audit", params={"action": "user."})
    items = r.json()["items"]
    assert items and items[0]["action"] == "user.create"
    assert "password" not in str(items[0]["data"]).lower()
    logins = (await boss.get("/api/v1/audit", params={"action": "auth.login"})).json()
    assert logins["total"] >= 1

    kor = await as_user(new_client, "kor", "koordinator")
    assert (await kor.get("/api/v1/audit")).status_code == 403


async def test_failed_login_is_audited(new_client, client):
    boss = await as_user(new_client, "boss", "hr_direktor")
    await login(client, "ghost", "whatever1")
    items = (await boss.get("/api/v1/audit", params={"action": "auth.login_failed"})).json()["items"]
    assert items and items[0]["actor_login"] == "ghost"


async def test_assignable_roles_endpoint_marks_what_actor_can_give(new_client):
    hr = await as_user(new_client, "hr", "hr_menejer")  # roles.read yo'q, lekin users.create bor
    assert (await hr.get("/api/v1/roles")).status_code == 403
    roles = {r["key"]: r["assignable"] for r in (await hr.get("/api/v1/users/assignable-roles")).json()}
    assert roles["stajyor"] is True and roles["farmasevt"] is True
    assert roles["tasischi"] is False and roles["hr_direktor"] is False and roles["direktor"] is False
    kor = await as_user(new_client, "k", "koordinator")
    assert (await kor.get("/api/v1/users/assignable-roles")).status_code == 403
