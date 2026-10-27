import pytest

from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)


async def as_user(new_client, login_name, role, **kw):
    uid = await make_user(login_name, role, **kw)
    c = new_client()
    assert (await login(c, login_name)).status_code == 200
    return c, uid


async def dept(c, name, **kw):
    r = await c.post("/api/v1/org/departments", json={"name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_permissions_for_org(new_client):
    mudir, _ = await as_user(new_client, "m", "mudir")
    assert (await mudir.get("/api/v1/org/tree")).status_code == 403
    kor, _ = await as_user(new_client, "k", "koordinator")
    assert (await kor.get("/api/v1/org/tree")).status_code == 200  # ko'rish mumkin
    assert (await kor.post("/api/v1/org/departments", json={"name": "X"})).status_code == 403
    hr, _ = await as_user(new_client, "hr", "hr_menejer")
    assert (await hr.post("/api/v1/org/departments", json={"name": "X"})).status_code == 403


async def test_create_department_with_default_positions_and_tree(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    root = await dept(boss, "Rahbariyat")
    child = await dept(boss, "Moliya", parent_id=root, kind="office", color="#12a150")

    pos = (await boss.get("/api/v1/org/positions", params={"department_id": child})).json()
    assert [p["name"] for p in pos] == ["Bo'lim boshlig'i", "Xodim"]

    tree = (await boss.get("/api/v1/org/tree")).json()
    assert tree["roots"][0]["name"] == "Rahbariyat"
    assert tree["roots"][0]["children"][0]["name"] == "Moliya"
    assert tree["roots"][0]["children"][0]["positions"] == 2
    assert tree["roots"][0]["children_count"] == 1


async def test_skip_default_positions(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    d = await dept(boss, "Bo'sh", create_default_positions=False)
    assert (await boss.get("/api/v1/org/positions", params={"department_id": d})).json() == []


async def test_duplicate_names_are_per_parent_and_case_insensitive(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    a = await dept(boss, "Moliya")
    r = await boss.post("/api/v1/org/departments", json={"name": "moliya"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "department_name_taken"
    # Boshqa ota ostida bir xil nom mumkin
    await dept(boss, "Moliya", parent_id=a)


async def test_head_assignment_notifies_and_validates(new_client):
    boss, boss_id = await as_user(new_client, "boss", "hr_direktor")
    head, head_id = await as_user(new_client, "head", "mudir")
    off_id = await make_user("off", "mudir", active=False)

    bad = await boss.post("/api/v1/org/departments", json={"name": "A", "head_user_id": off_id})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "unknown_user"
    assert (await boss.post("/api/v1/org/departments", json={"name": "A", "head_user_id": 9999})).status_code == 400

    d = await dept(boss, "Logistika", head_user_id=head_id)
    tree = (await boss.get("/api/v1/org/tree")).json()
    assert tree["roots"][0]["head"]["full_name"] == "Head"
    kinds = [n["kind"] for n in (await head.get("/api/v1/notifications")).json()["items"]]
    assert "org.head_assigned" in kinds

    # Boshliqni olib tashlash (null)
    r = await boss.patch(f"/api/v1/org/departments/{d}", json={"head_user_id": None})
    assert r.status_code == 200
    assert (await boss.get("/api/v1/org/tree")).json()["roots"][0]["head"] is None


async def test_assigning_yourself_does_not_notify(new_client):
    boss, boss_id = await as_user(new_client, "boss", "hr_direktor")
    await dept(boss, "Moliya", head_user_id=boss_id)
    assert (await boss.get("/api/v1/notifications")).json()["total"] == 0


async def test_cannot_create_cycle_or_exceed_depth(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    a = await dept(boss, "A")
    b = await dept(boss, "B", parent_id=a)
    c = await dept(boss, "C", parent_id=b)

    for target in (a, b, c):  # o'zi yoki avlodiga ko'chirib bo'lmaydi
        r = await boss.patch(f"/api/v1/org/departments/{a}", json={"parent_id": target})
        assert r.status_code == 409 and r.json()["detail"]["code"] == "cycle"

    ids = [a, b, c]
    for i in range(3, 6):  # chuqurlik 6 gacha
        ids.append(await dept(boss, f"N{i}", parent_id=ids[-1]))
    r = await boss.post("/api/v1/org/departments", json={"name": "Juda chuqur", "parent_id": ids[-1]})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "too_deep"

    # Daraxtni chuqurroq joyga ko'chirish ham chegarani buzmasligi kerak
    extra = await dept(boss, "Extra")
    r = await boss.patch(f"/api/v1/org/departments/{a}", json={"parent_id": extra})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "too_deep"


async def test_move_to_root_and_update_fields(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    a = await dept(boss, "A")
    b = await dept(boss, "B", parent_id=a, color="#112233")
    r = await boss.patch(f"/api/v1/org/departments/{b}", json={"parent_id": None, "name": "  B2 ", "color": None, "is_active": False})
    assert r.status_code == 200
    flat = {d["id"]: d for d in (await boss.get("/api/v1/org/departments")).json()}
    assert flat[b]["parent_id"] is None and flat[b]["name"] == "B2"
    assert flat[b]["color"] is None and flat[b]["is_active"] is False and flat[b]["depth"] == 1


async def test_delete_department_rules(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    a = await dept(boss, "A")
    b = await dept(boss, "B", parent_id=a)
    r = await boss.delete(f"/api/v1/org/departments/{a}")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "has_children"

    await boss.post("/api/v1/branches", json={"name": "F1", "department_id": b})
    r = await boss.delete(f"/api/v1/org/departments/{b}")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "has_branches"

    c = await dept(boss, "C")
    assert (await boss.delete(f"/api/v1/org/departments/{c}")).status_code == 204
    # Lavozimlari ham o'chgan
    assert (await boss.get("/api/v1/org/positions", params={"department_id": c})).json() == []


async def test_positions_crud_and_uniqueness(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    d = await dept(boss, "Omborxona", create_default_positions=False)
    r = await boss.post("/api/v1/org/positions", json={"name": "Omborchi", "department_id": d})
    pid = r.json()["id"]
    dup = await boss.post("/api/v1/org/positions", json={"name": "OMBORCHI", "department_id": d})
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "position_name_taken"
    # Umumiy lavozim (bo'limsiz) va boshqa bo'limda bir xil nom
    other = await dept(boss, "Boshqa", create_default_positions=False)
    assert (await boss.post("/api/v1/org/positions", json={"name": "Omborchi", "department_id": other})).status_code == 201
    assert (await boss.post("/api/v1/org/positions", json={"name": "Omborchi"})).status_code == 201

    assert (await boss.patch(f"/api/v1/org/positions/{pid}", json={"name": "Katta omborchi", "is_active": False})).status_code == 200
    p = (await boss.get("/api/v1/org/positions", params={"department_id": d})).json()[0]
    assert p["name"] == "Katta omborchi" and p["is_active"] is False
    only_active = (await boss.get("/api/v1/org/positions", params={"department_id": d, "include_inactive": "false"})).json()
    assert only_active == []
    assert (await boss.post("/api/v1/org/positions", json={"name": "X", "department_id": 9999})).status_code == 404
    assert (await boss.delete(f"/api/v1/org/positions/{pid}")).status_code == 204


async def test_assignable_users_needs_manage_permission_not_users_read(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    await make_user("sardor", "mudir", name="Sardor Aliyev")
    await make_user("gone", "mudir", active=False, name="Sardor Eski")
    r = (await boss.get("/api/v1/org/assignable-users", params={"q": "sardor"})).json()
    assert [u["full_name"] for u in r] == ["Sardor Aliyev"]  # faol foydalanuvchilar
    kor, _ = await as_user(new_client, "k", "koordinator")
    assert (await kor.get("/api/v1/org/assignable-users")).status_code == 403


async def test_org_changes_are_audited(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    d = await dept(boss, "Moliya")
    await boss.patch(f"/api/v1/org/departments/{d}", json={"name": "Moliya bo'limi"})
    items = (await boss.get("/api/v1/audit", params={"action": "org."})).json()["items"]
    actions = [i["action"] for i in items]
    assert "org.department_create" in actions and "org.department_update" in actions
    upd = next(i for i in items if i["action"] == "org.department_update")
    assert upd["data"]["name"] == {"from": "Moliya", "to": "Moliya bo'limi"}


async def test_client_can_override_default_positions(new_client, app):
    app.state.client_config.settings["org"] = {"default_positions": ["Mudir", "Mudir", "  ", "Sotuvchi"]}
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    d = await dept(boss, "Savdo")
    names = [p["name"] for p in (await boss.get("/api/v1/org/positions", params={"department_id": d})).json()]
    assert names == ["Mudir", "Sotuvchi"]  # takror va bo'shlar tashlanadi
