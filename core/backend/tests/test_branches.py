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


async def test_branch_permissions(new_client):
    kor, _ = await as_user(new_client, "k", "koordinator")
    assert (await kor.get("/api/v1/branches")).status_code == 200
    assert (await kor.post("/api/v1/branches", json={"name": "F"})).status_code == 403
    mudir, _ = await as_user(new_client, "m", "mudir")
    assert (await mudir.get("/api/v1/branches")).status_code == 403


async def test_create_get_update_delete_branch(new_client):
    boss, boss_id = await as_user(new_client, "boss", "hr_direktor")
    mgr, mgr_id = await as_user(new_client, "mgr", "mudir", name="Mudir Birinchi")
    coord, coord_id = await as_user(new_client, "crd", "koordinator", name="Koord Birinchi")

    r = await boss.post("/api/v1/branches", json={
        "number": 16, "name": "1-gor bolnitsa", "district": "Yunusobod", "latitude": 41.36, "longitude": 69.28,
        "manager_user_id": mgr_id, "coordinator_user_id": coord_id,
    })  # fmt: skip
    assert r.status_code == 201
    b = r.json()
    assert b["number"] == 16 and b["manager_name"] == "Mudir Birinchi" and b["geofence_radius_m"] == 100
    assert b["latitude"] == 41.36

    # Mudir va koordinatorga bildirishnoma
    assert "branch.manager_assigned" in [n["kind"] for n in (await mgr.get("/api/v1/notifications")).json()["items"]]
    assert "branch.coordinator_assigned" in [n["kind"] for n in (await coord.get("/api/v1/notifications")).json()["items"]]

    r = await boss.patch(f"/api/v1/branches/{b['id']}", json={"name": "Yangi nom", "geofence_radius_m": 150, "phone": " +998901112233 "})
    assert r.json()["name"] == "Yangi nom" and r.json()["geofence_radius_m"] == 150 and r.json()["phone"] == "+998901112233"

    # Joylashuvni olib tashlash
    r = await boss.patch(f"/api/v1/branches/{b['id']}", json={"latitude": None, "longitude": None, "manager_user_id": None})
    assert r.json()["latitude"] is None and r.json()["manager_name"] is None

    assert (await boss.delete(f"/api/v1/branches/{b['id']}")).status_code == 204
    assert (await boss.get(f"/api/v1/branches/{b['id']}")).status_code == 404


async def test_branch_validation(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    post = lambda **kw: boss.post("/api/v1/branches", json={"name": "F", **kw})  # noqa: E731
    assert (await post(latitude=41.3)).status_code == 422  # faqat bittasi
    assert (await post(latitude=95, longitude=69)).status_code == 422
    assert (await post(latitude=41, longitude=200)).status_code == 422
    assert (await post(geofence_radius_m=5)).status_code == 422
    assert (await post(geofence_radius_m=99999)).status_code == 422
    assert (await post(number=0)).status_code == 422
    assert (await boss.post("/api/v1/branches", json={"name": ""})).status_code == 422
    assert (await post(manager_user_id=9999)).status_code == 400
    assert (await post(department_id=9999)).status_code == 400
    off = await make_user("off", "mudir", active=False)
    assert (await post(manager_user_id=off)).status_code == 400  # faol bo'lmagan mudir

    p = await boss.post("/api/v1/branches", json={"name": "P"})
    pid = p.json()["id"]
    assert (await boss.patch(f"/api/v1/branches/{pid}", json={"latitude": 41.3})).status_code == 422


async def test_branch_number_is_unique(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    await boss.post("/api/v1/branches", json={"number": 5, "name": "A"})
    dup = await boss.post("/api/v1/branches", json={"number": 5, "name": "B"})
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "branch_number_taken"
    other = (await boss.post("/api/v1/branches", json={"number": 6, "name": "C"})).json()
    clash = await boss.patch(f"/api/v1/branches/{other['id']}", json={"number": 5})
    assert clash.status_code == 409
    # Raqamsiz filiallar ko'p bo'lishi mumkin
    assert (await boss.post("/api/v1/branches", json={"name": "N1"})).status_code == 201
    assert (await boss.post("/api/v1/branches", json={"name": "N2"})).status_code == 201


async def test_list_filters_search_pagination_and_summary(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    _, mgr_id = await as_user(new_client, "mgr", "mudir")
    _, crd_id = await as_user(new_client, "crd", "koordinator")
    for n in range(1, 8):
        await boss.post("/api/v1/branches", json={
            "number": n, "name": f"Dorixona {n}", "district": "Yunusobod" if n % 2 else "Chilonzor",
            "manager_user_id": mgr_id if n == 1 else None,
            "coordinator_user_id": crd_id if n <= 3 else None,
            "latitude": 41.3 if n <= 2 else None, "longitude": 69.2 if n <= 2 else None,
        })  # fmt: skip
    await boss.post("/api/v1/branches", json={"name": "Raqamsiz", "is_active": False})

    r = (await boss.get("/api/v1/branches", params={"size": 3, "page": 2})).json()
    assert r["total"] == 8 and len(r["items"]) == 3
    assert [b["number"] for b in r["items"]] == [4, 5, 6]  # raqam bo'yicha, raqamsizlar oxirida
    assert r["summary"] == {"total": 8, "with_manager": 1, "with_geo": 2, "active": 7}

    q = lambda **kw: boss.get("/api/v1/branches", params=kw)  # noqa: E731
    assert (await q(q="№3")).json()["items"][0]["name"] == "Dorixona 3"
    assert {b["district"] for b in (await q(q="chilonzor")).json()["items"]} == {"Chilonzor"}
    assert (await q(coordinator_id=crd_id)).json()["total"] == 3
    assert (await q(manager_id=mgr_id)).json()["total"] == 1
    assert (await q(no_manager="true")).json()["total"] == 7
    assert (await q(no_geo="true")).json()["total"] == 6
    assert (await q(active="false")).json()["total"] == 1


async def test_map_endpoint_only_returns_located_branches(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    await boss.post("/api/v1/branches", json={"number": 1, "name": "Bor", "latitude": 41.3, "longitude": 69.2})
    await boss.post("/api/v1/branches", json={"number": 2, "name": "Yo'q"})
    pts = (await boss.get("/api/v1/branches/map")).json()
    assert [p["name"] for p in pts] == ["Bor"] and pts[0]["radius"] == 100


async def test_bulk_import_dry_run_then_apply_upserts_by_number(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    await boss.post("/api/v1/branches", json={"number": 1, "name": "Eski nom", "district": "Saqlanadi"})

    rows = [
        {"number": 1, "name": "Yangi nom", "latitude": 41.3, "longitude": 69.2},
        {"number": 2, "name": "Ikkinchi"},
        {"name": "Raqamsiz"},
    ]
    dry = (await boss.post("/api/v1/branches/bulk", json={"rows": rows, "dry_run": True})).json()
    assert dry == {"created": 2, "updated": 1, "errors": [], "applied": False}
    assert (await boss.get("/api/v1/branches")).json()["total"] == 1  # hech narsa yozilmadi

    done = (await boss.post("/api/v1/branches/bulk", json={"rows": rows, "dry_run": False})).json()
    assert done["applied"] is True
    items = {b["name"]: b for b in (await boss.get("/api/v1/branches")).json()["items"]}
    assert len(items) == 3 and items["Yangi nom"]["latitude"] == 41.3
    assert items["Yangi nom"]["district"] == "Saqlanadi"  # berilmagan maydonlarga tegilmaydi


async def test_bulk_import_is_all_or_nothing(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    rows = [
        {"number": 1, "name": "OK"},
        {"number": 2, "name": ""},
        {"number": 1, "name": "Takror"},
        {"name": "X", "latitude": 41.0},
        {"name": "Y", "latitude": 99, "longitude": 10},
        {"name": "Z", "geofence_radius_m": 1},
    ]
    r = (await boss.post("/api/v1/branches/bulk", json={"rows": rows, "dry_run": False})).json()
    assert r["applied"] is False
    assert {(e["row"], e["code"]) for e in r["errors"]} == {
        (2, "name_required"), (3, "number_duplicate"), (4, "coords_pair"), (5, "coords_range"), (6, "radius_range"),
    }  # fmt: skip
    assert (await boss.get("/api/v1/branches")).json()["total"] == 0
    too_many = await boss.post("/api/v1/branches/bulk", json={"rows": [{"name": "a"}] * 1001})
    assert too_many.status_code == 422


async def test_new_default_permissions_are_granted_once_and_removals_stick(new_client):
    """Yangi versiyadagi default ruxsat mavjud rolga bir marta beriladi; olib tashlansa qaytmaydi."""
    from sqlalchemy import delete, select

    from app.db import SessionLocal
    from app.models.auth import Role, RolePermission
    from app.services.seed import ensure_roles

    async with SessionLocal() as s:
        role = await s.scalar(select(Role).where(Role.key == "koordinator"))
        await s.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        await s.commit()
        await ensure_roles(s)  # allaqachon berilgan deb yozilgan: qaytarilmaydi
        s.expire_all()
        role = await s.scalar(select(Role).where(Role.key == "koordinator"))
        assert role.permission_keys == set()
