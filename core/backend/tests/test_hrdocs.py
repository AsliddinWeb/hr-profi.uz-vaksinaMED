import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.hrdocs import HrDocument
from app.services import hrdocs as svc
from tests.conftest import PASSWORD, login, make_user  # noqa: F401

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

H = "/api/v1/hrdocs"


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def notes(c):
    return (await c.get("/api/v1/notifications")).json()["items"]


def doc(**kw):
    return {"category": "policy", "title": "Ichki tartib qoidalari", "body": "1-modda. Ish vaqti 9:00 dan 18:00 gacha.", "requires_ack": True, **kw}


async def test_default_cards_idempotent(new_client):
    async with SessionLocal() as s:
        assert await svc.ensure_default_docs(s) == len(svc.DEFAULT_DOCS)
        assert await svc.ensure_default_docs(s) == 0
        rows = (await s.scalars(select(HrDocument))).all()
        assert len(rows) == 24 and all(r.status == "draft" and r.version == 0 for r in rows)


async def test_lifecycle_visibility_and_ack(new_client):
    hrd, _ = await as_user(new_client, "hrd", "hr_direktor")
    far, _ = await as_user(new_client, "far", "farmasevt")
    mudir, _ = await as_user(new_client, "mudir", "mudir")
    assert (await far.post(H, json=doc())).status_code == 403
    r = await hrd.post(H, json=doc(roles=["farmasevt"]))
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    assert r.json()["status"] == "draft" and r.json()["version"] == 0
    # qoralamani xodim ko'rmaydi
    assert (await far.get(f"{H}/{did}")).status_code == 404
    assert (await far.get(H)).json()["items"] == []
    # bo'sh hujjatni e'lon qilib bo'lmaydi
    empty = (await hrd.post(H, json=doc(title="Bo'sh", body=None))).json()
    assert (await hrd.post(f"{H}/{empty['id']}/publish", json={})).json()["detail"]["code"] == "document_empty"
    p = await hrd.post(f"{H}/{did}/publish", json={"note": "Birinchi versiya"})
    assert p.status_code == 200 and p.json()["version"] == 1 and p.json()["status"] == "published"
    # faqat farmasevt roliga ko'rinadi, mudirga yo'q
    got = (await far.get(H)).json()
    assert [i["id"] for i in got["items"]] == [did] and got["pending_ack"] == 1 and got["items"][0]["needs_ack"]
    assert (await mudir.get(f"{H}/{did}")).status_code == 404
    assert any(n["kind"] == "hrdoc.published" for n in await notes(far))
    assert not any(n["kind"] == "hrdoc.published" for n in await notes(mudir))
    assert (await far.get(f"{H}/pending/count")).json() == {"count": 1}
    # tanishdim
    a = await far.post(f"{H}/{did}/ack")
    assert a.status_code == 200 and a.json()["needs_ack"] is False and a.json()["ack"]["version"] == 1
    assert (await far.get(f"{H}/pending/count")).json() == {"count": 0}
    st = (await hrd.get(f"{H}/{did}/acks")).json()
    assert st["total"] == 1 and len(st["done"]) == 1 and st["pending"] == []
    # yangi versiya: tasdiq eskiradi
    await hrd.put(f"{H}/{did}", json=doc(roles=["farmasevt"], body="Yangi tahrir"))
    assert (await far.get(f"{H}/{did}")).json()["needs_ack"] is False  # kichik tahrir versiyani o'zgartirmaydi
    p2 = await hrd.post(f"{H}/{did}/publish", json={"note": "Muhim o'zgarish"})
    assert p2.json()["version"] == 2
    assert (await far.get(f"{H}/{did}")).json()["needs_ack"] is True
    assert len((await hrd.get(f"{H}/{did}/versions")).json()) == 2
    assert (await far.get(f"{H}/{did}/versions")).status_code == 403
    assert (await hrd.get(f"{H}/{did}/acks")).json()["pending"][0]["user"]["name"] == "Far"
    # e'lon qilinganni o'chirib bo'lmaydi; qoralama o'chadi
    assert (await hrd.delete(f"{H}/{did}")).json()["detail"]["code"] == "already_published"
    assert (await hrd.delete(f"{H}/{empty['id']}")).status_code == 204
    assert (await hrd.post(H, json=doc(roles=["yoq-rol"]))).json()["detail"]["code"] == "unknown_role"


async def test_file_upload_and_download(new_client, app):
    hrd, _ = await as_user(new_client, "hrd", "hr_direktor")
    far, _ = await as_user(new_client, "far", "farmasevt")
    did = (await hrd.post(H, json=doc(body=None, requires_ack=False))).json()["id"]
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    up = await hrd.put(f"{H}/{did}/file", files={"file": ("nizom.pdf", pdf, "application/pdf")})
    assert up.status_code == 200 and up.json()["has_file"] and up.json()["file_name"] == "nizom.pdf"
    assert (await hrd.put(f"{H}/{did}/file", files={"file": ("x.exe", b"MZ\x90\x00", "application/octet-stream")})).status_code == 415
    assert (await far.put(f"{H}/{did}/file", files={"file": ("n.pdf", pdf, "application/pdf")})).status_code == 403
    assert (await far.get(f"{H}/{did}/file")).status_code == 404  # qoralama
    await hrd.post(f"{H}/{did}/publish", json={})
    dl = await far.get(f"{H}/{did}/file")
    assert dl.status_code == 200 and dl.content == pdf and "nizom.pdf" in dl.headers["content-disposition"]
