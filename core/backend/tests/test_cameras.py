import asyncio
import base64
import io

import pytest

from app.db import SessionLocal
from app.models.org import Branch
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200


async def _listener():
    srv = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    return srv, srv.sockets[0].getsockname()[1]


async def test_ip_camera_status_import_and_station(new_client):
    await make_user("camadm", "hr_direktor")
    c = new_client()
    assert (await login(c, "camadm")).status_code == 200
    async with SessionLocal() as s:
        b = Branch(name="Filial 7", number=7)
        s.add(b)
        await s.commit()
        bid = b.id
    srv, port = await _listener()
    try:
        up = (await c.post("/api/v1/cameras", json={"name": "Kirish", "branch_id": bid, "host": "127.0.0.1", "port": port})).json()
        down = (await c.post("/api/v1/cameras", json={"name": "Kassa", "branch_id": bid, "host": "127.0.0.1", "port": 1})).json()
        assert (await c.post("/api/v1/cameras", json={"name": "IPsiz", "kind": "ip"})).status_code == 400
        assert (await c.post(f"/api/v1/cameras/{up['id']}/check")).json()["status"] == "online"
        assert (await c.post(f"/api/v1/cameras/{down['id']}/check")).json()["status"] == "offline"
    finally:
        srv.close()
    s = (await c.get("/api/v1/cameras/summary")).json()
    assert s["online"] == 1 and s["offline"] == 1 and s["branches_with_offline"] == 1 and s["worst_branches"][0]["name"] == "Filial 7"
    assert (await c.get("/api/v1/cameras", params={"status": "offline"})).json()["total"] == 1

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Filial raqami", "Filial nomi", "Kamera nomi", "Joyi", "IP", "Port", "Brend", "Model"])
    ws.append([7, None, "Ombor", "Ombor", "10.0.0.5", 554, "Dahua", None])
    ws.append([7, None, "Ombor dublikat", None, "10.0.0.5", 554, None, None])
    ws.append([999, None, "Yo'q filial", None, "10.0.0.6", None, None, None])
    buf = io.BytesIO()
    wb.save(buf)
    r = (await c.post("/api/v1/cameras/import", files={"file": ("k.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})).json()
    assert r["added"] == 1 and r["skipped"] == 1 and r["errors"][0]["error"] == "branch_not_found"

    st = (await c.post("/api/v1/cameras", json={"name": "Kassa kompyuteri", "kind": "webcam", "branch_id": bid})).json()
    token = st["station_url"].rsplit("/", 1)[1]
    pub = new_client()
    assert (await pub.get(f"/api/v1/public/camera/{token}")).json()["name"] == "Kassa kompyuteri"
    snap = base64.b64encode(JPEG).decode()
    assert (await pub.post(f"/api/v1/public/camera/{token}/beat", json={"device": "Chrome", "snapshot": "data:image/jpeg;base64," + snap})).json()["status"] == "online"
    img = await c.get(f"/api/v1/cameras/{st['id']}/snapshot")
    assert img.status_code == 200 and img.content.startswith(b"\xff\xd8")
    assert (await pub.post(f"/api/v1/public/camera/{token}/beat", json={"snapshot": base64.b64encode(b"notjpeg").decode()})).status_code == 400
    assert (await pub.post(f"/api/v1/public/camera/{token}/stop")).json()["ok"] is True
    assert (await c.get(f"/api/v1/cameras/{st['id']}/snapshot")).status_code == 404

    await make_user("camfarm", "farmasevt")
    f = new_client()
    assert (await login(f, "camfarm")).status_code == 200
    assert (await f.get("/api/v1/cameras/summary")).status_code == 403
