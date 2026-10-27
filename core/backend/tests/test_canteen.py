from datetime import date, datetime

import pytest

from app.db import SessionLocal
from app.models.employees import Employee
from app.services import canteen as svc
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

C = "/api/v1/canteen"
NOW = datetime(2026, 11, 10, 13, 0, tzinfo=tz())
TODAY = "2026-11-10"
DISHES = [{"name": "Mastava", "kind": "soup"}, {"name": "Palov", "kind": "main"}, {"name": "Achchiq-chuchuk", "kind": "salad"}]


@pytest.fixture
def clock(monkeypatch):
    fn = lambda: NOW  # noqa: E731
    monkeypatch.setattr("app.api.canteen.now", fn)


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def mk_emp(name, user_id=None, status="active"):
    async with SessionLocal() as s:
        e = Employee(last_name=name, first_name="X", full_name=f"{name} X", user_id=user_id, status=status)
        s.add(e)
        await s.commit()
        return e.id


async def setup(new_client):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    mgr, _ = await as_user(new_client, "menejer", "hr_menejer")
    boss, _ = await as_user(new_client, "boss", "direktor")
    users = {}
    for n in ("ali", "vali", "sami"):
        c, uid = await as_user(new_client, n, "farmasevt")
        await mk_emp(n.title(), uid)
        users[n] = c
    nobody, _ = await as_user(new_client, "yolgiz", "farmasevt")  # xodim kartasi yo'q
    return {"hr": hr, "mgr": mgr, "boss": boss, **users, "nobody": nobody}


async def mk_menu(c, day=TODAY, dishes=DISHES, **kw):
    r = await c.post(f"{C}/menus", json={"menu_date": day, "dishes": dishes, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_qr_token_unit():
    t = svc.make_qr_token(0)
    assert svc.qr_valid(t, 0) and not svc.qr_valid(t, 1) and not svc.qr_valid(None, 0) and not svc.qr_valid("0.abc", 0) and not svc.qr_valid("x", 0)
    assert svc.make_qr_token(1) != t
    assert svc.rating_open(date(2026, 11, 10), date(2026, 11, 10), 1) and svc.rating_open(date(2026, 11, 9), date(2026, 11, 10), 1)
    assert not svc.rating_open(date(2026, 11, 8), date(2026, 11, 10), 1) and not svc.rating_open(date(2026, 11, 11), date(2026, 11, 10), 1)


async def test_menu_crud_and_permissions(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    assert (await ctx["ali"].post(f"{C}/menus", json={"menu_date": TODAY, "dishes": DISHES})).status_code == 403
    assert (await ctx["boss"].post(f"{C}/menus", json={"menu_date": TODAY, "dishes": DISHES})).status_code == 403
    assert (await hr.post(f"{C}/menus", json={"menu_date": TODAY, "dishes": []})).status_code == 422
    assert (await hr.post(f"{C}/menus", json={"menu_date": TODAY, "dishes": [{"name": "X", "kind": "pizza"}]})).status_code == 422
    m = await mk_menu(hr, note="Juma")
    assert [d["name"] for d in m["dishes"]] == ["Mastava", "Palov", "Achchiq-chuchuk"] and m["can_rate"] is True
    assert (await hr.post(f"{C}/menus", json={"menu_date": TODAY, "dishes": DISHES})).json()["detail"]["code"] == "menu_exists"
    # xodim bugungi menyuni ko'radi, lekin reytingni emas
    mine = (await ctx["ali"].get(f"{C}/menus/today")).json()
    assert mine["id"] == m["id"] and mine["rating"] is None and mine["mine"] == {"overall": None, "dishes": {}}
    assert (await ctx["boss"].get(f"{C}/menus/today")).json()["rating"] == {"avg": None, "count": 0}
    assert (await ctx["ali"].get(f"{C}/menus", params={"start": TODAY, "end": TODAY})).json()[0]["id"] == m["id"]
    assert (await hr.get(f"{C}/menus", params={"start": "2026-01-01", "end": "2026-12-31"})).status_code == 400
    # tahrirlash: taom id si saqlanadi, yangi qo'shiladi, olib tashlanadi
    d0 = m["dishes"][0]
    r = await hr.put(f"{C}/menus/{m['id']}", json={"menu_date": TODAY, "dishes": [{"id": d0["id"], "name": "Mastava (yangi)", "kind": "soup"}, {"name": "Kompot", "kind": "drink"}]})
    names = [(d["id"], d["name"]) for d in r.json()["dishes"]]
    assert names[0] == (d0["id"], "Mastava (yangi)") and names[1][1] == "Kompot" and len(names) == 2
    other = await mk_menu(hr, day="2026-11-11")
    assert (await hr.put(f"{C}/menus/{other['id']}", json={"menu_date": TODAY, "dishes": DISHES})).json()["detail"]["code"] == "menu_exists"
    assert (await hr.delete(f"{C}/menus/{other['id']}")).status_code == 204
    assert (await hr.get("/api/v1/audit", params={"action": "canteen.menu_create"})).json()["total"] == 2


async def test_rating_rules(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    m = await mk_menu(hr)
    mid, dids = m["id"], [d["id"] for d in m["dishes"]]
    ali = ctx["ali"]
    assert (await ali.post(f"{C}/menus/{mid}/rate", json={})).json()["detail"]["code"] == "nothing_to_rate"
    assert (await ali.post(f"{C}/menus/{mid}/rate", json={"overall": {"stars": 6}})).status_code == 422
    assert (await ctx["nobody"].post(f"{C}/menus/{mid}/rate", json={"overall": {"stars": 5}})).json()["detail"]["code"] == "no_employee"
    assert (await ali.post(f"{C}/menus/{mid}/rate", json={"dishes": [{"dish_id": 99999, "stars": 5}]})).json()["detail"]["code"] == "unknown_dish"
    r = await ali.post(f"{C}/menus/{mid}/rate", json={"overall": {"stars": 4, "comment": "Yaxshi"}, "dishes": [{"dish_id": dids[0], "stars": 5}, {"dish_id": dids[1], "stars": 3}]})
    assert r.status_code == 200
    assert r.json()["mine"]["overall"]["stars"] == 4 and r.json()["mine"]["dishes"] == {str(dids[0]): {"stars": 5}, str(dids[1]): {"stars": 3}} and r.json()["rating"] is None
    # qayta yuborish yangilaydi (ikkilanmaydi); taomni olib tashlash
    r = await ali.post(f"{C}/menus/{mid}/rate", json={"overall": {"stars": 5}, "dishes": [{"dish_id": dids[1], "stars": None}]})
    assert r.json()["mine"]["overall"]["stars"] == 5 and list(r.json()["mine"]["dishes"]) == [str(dids[0])]
    await ctx["vali"].post(f"{C}/menus/{mid}/rate", json={"overall": {"stars": 3}, "dishes": [{"dish_id": dids[0], "stars": 4}]})
    s = (await hr.get(f"{C}/menus/{mid}")).json()
    assert s["rating"] == {"avg": 4.0, "count": 2} and s["dishes"][0]["avg"] == 4.5 and s["dishes"][0]["count"] == 2 and s["dishes"][1]["avg"] is None
    # chetga qaytarib olish
    assert (await ctx["vali"].delete(f"{C}/menus/{mid}/rate")).status_code == 204
    assert (await hr.get(f"{C}/menus/{mid}")).json()["rating"]["count"] == 1
    # menyu o'chirilmaydi, sana o'zgarmaydi
    assert (await hr.delete(f"{C}/menus/{mid}")).json()["detail"]["code"] == "menu_has_ratings"
    assert (await hr.put(f"{C}/menus/{mid}", json={"menu_date": "2026-11-20", "dishes": DISHES})).json()["detail"]["code"] == "menu_has_ratings"

    # baholash oynasi: ertangi menyuga yo'q, 2 kun oldingiga yo'q, kechagisiga bor
    future = await mk_menu(hr, day="2026-11-11")
    old = await mk_menu(hr, day="2026-11-08")
    yest = await mk_menu(hr, day="2026-11-09")
    assert (await ali.post(f"{C}/menus/{future['id']}/rate", json={"overall": {"stars": 5}})).json()["detail"]["code"] == "rating_closed"
    assert (await ali.post(f"{C}/menus/{old['id']}/rate", json={"overall": {"stars": 5}})).json()["detail"]["code"] == "rating_closed"
    assert (await ali.post(f"{C}/menus/{yest['id']}/rate", json={"overall": {"stars": 5}})).status_code == 200
    await hr.put(f"{C}/settings", json={"require_qr": False, "rating_days": 3})
    assert (await ali.post(f"{C}/menus/{old['id']}/rate", json={"overall": {"stars": 2}})).status_code == 200
    # past baho menejerlarga xabar
    assert "canteen.low_rating" in [n["kind"] for n in (await ctx["mgr"].get("/api/v1/notifications")).json()["items"]]


async def test_qr_and_settings(new_client, clock):
    ctx = await setup(new_client)
    hr, ali = ctx["hr"], ctx["ali"]
    m = await mk_menu(hr)
    assert (await ali.get(f"{C}/qr")).status_code == 403
    q = (await hr.get(f"{C}/qr")).json()
    assert q["url"].endswith(f"/canteen/rate?t={q['token']}") and q["svg"].startswith("<svg")
    assert (await ali.get(f"{C}/qr/resolve", params={"t": q["token"]})).json()["menu"]["id"] == m["id"]
    assert (await ali.get(f"{C}/qr/resolve", params={"t": "0.xxxx"})).json()["detail"]["code"] == "qr_invalid"
    assert (await ali.get(f"{C}/settings")).status_code == 403
    assert (await hr.put(f"{C}/settings", json={"require_qr": True, "rating_days": 1})).json() == {"require_qr": True, "rating_days": 1}
    assert (await hr.put(f"{C}/settings", json={"require_qr": True, "rating_days": 99})).status_code == 422
    # QR majburiy: tokensiz rad, tokenli o'tadi va "QR orqali" deb belgilanadi
    assert (await ali.post(f"{C}/menus/{m['id']}/rate", json={"overall": {"stars": 5}})).json()["detail"]["code"] == "qr_required"
    assert (await ali.post(f"{C}/menus/{m['id']}/rate", json={"overall": {"stars": 5}, "qr": "0.bad"})).json()["detail"]["code"] == "qr_required"
    assert (await ali.post(f"{C}/menus/{m['id']}/rate", json={"overall": {"stars": 5}, "qr": q["token"]})).status_code == 200
    a = (await hr.get(f"{C}/analytics", params={"start": TODAY, "end": TODAY})).json()
    assert a["kpis"]["via_qr"] == 1
    # QR almashtirilsa eskisi ishlamaydi
    assert (await hr.post(f"{C}/qr/rotate")).json() == {"epoch": 1}
    assert (await ctx["vali"].post(f"{C}/menus/{m['id']}/rate", json={"overall": {"stars": 5}, "qr": q["token"]})).json()["detail"]["code"] == "qr_required"
    assert (await ali.get(f"{C}/qr/resolve", params={"t": q["token"]})).json()["detail"]["code"] == "qr_invalid"
    q2 = (await hr.get(f"{C}/qr")).json()
    assert q2["token"] != q["token"] and (await ctx["vali"].post(f"{C}/menus/{m['id']}/rate", json={"overall": {"stars": 4}, "qr": q2["token"]})).status_code == 200


async def test_comments_replies_and_analytics(new_client, clock):
    ctx = await setup(new_client)
    hr, mgr, boss = ctx["hr"], ctx["mgr"], ctx["boss"]
    m = await mk_menu(hr)
    yest = await mk_menu(hr, day="2026-11-09", dishes=[{"name": "mastava", "kind": "soup"}, {"name": "Lag'mon", "kind": "main"}])
    dids = [d["id"] for d in m["dishes"]]
    ydids = [d["id"] for d in yest["dishes"]]
    await ctx["ali"].post(f"{C}/menus/{m['id']}/rate", json={"overall": {"stars": 5, "comment": "Mazali"}, "dishes": [{"dish_id": dids[0], "stars": 5}, {"dish_id": dids[1], "stars": 4}]})
    await ctx["vali"].post(f"{C}/menus/{m['id']}/rate", json={"overall": {"stars": 1, "comment": "Sovuq edi", "anonymous": True}, "dishes": [{"dish_id": dids[0], "stars": 2}]})
    await ctx["sami"].post(f"{C}/menus/{m['id']}/rate", json={"overall": {"stars": 3}})
    await ctx["ali"].post(f"{C}/menus/{yest['id']}/rate", json={"overall": {"stars": 4}, "dishes": [{"dish_id": ydids[0], "stars": 3}, {"dish_id": ydids[1], "stars": 5}]})

    # izohlar: direktor ko'radi, anonim ismi faqat boshqaruvchiga
    r = (await boss.get(f"{C}/ratings", params={"start": "2026-11-01", "end": TODAY})).json()
    assert r["total"] == 2 and {i["comment"] for i in r["items"]} == {"Mazali", "Sovuq edi"}
    anon = next(i for i in r["items"] if i["comment"] == "Sovuq edi")
    assert anon["employee"] is None and next(i for i in r["items"] if i["comment"] == "Mazali")["employee"] == "Ali X"
    assert (await mgr.get(f"{C}/ratings", params={"start": "2026-11-01", "end": TODAY})).json()["items"][1]["employee"] in ("Vali X", "Ali X")
    assert (await ctx["ali"].get(f"{C}/ratings", params={"start": "2026-11-01", "end": TODAY})).status_code == 403
    low = (await hr.get(f"{C}/ratings", params={"start": "2026-11-01", "end": TODAY, "max_stars": 2})).json()
    assert low["total"] == 1 and low["items"][0]["employee"] == "Vali X"  # boshqaruvchi anonim ismini ko'radi
    assert (await hr.get(f"{C}/ratings", params={"start": "2026-11-01", "end": TODAY, "commented": "false"})).json()["total"] == 4

    # javob
    rid = low["items"][0]["id"]
    assert (await boss.post(f"{C}/ratings/{rid}/reply", json={"reply": "Rahmat"})).status_code == 403
    assert (await mgr.post(f"{C}/ratings/{rid}/reply", json={"reply": "Kechirasiz, tuzatamiz"})).json()["reply"] == "Kechirasiz, tuzatamiz"
    assert "canteen.reply" in [n["kind"] for n in (await ctx["vali"].get("/api/v1/notifications")).json()["items"]]
    assert (await hr.get(f"{C}/ratings", params={"start": "2026-11-01", "end": TODAY, "unanswered": "true"})).json()["total"] == 1
    assert (await ctx["vali"].get(f"{C}/menus/{m['id']}")).json()["mine"]["overall"]["reply"] == "Kechirasiz, tuzatamiz"

    a = (await boss.get(f"{C}/analytics", params={"start": "2026-11-01", "end": TODAY})).json()
    k = a["kpis"]
    assert k["menus"] == 2 and k["ratings"] == 4 and k["raters"] == 3 and k["avg"] == 3.25 and k["low_share"] == 0.25
    assert k["commented"] == 2 and k["unanswered"] == 1 and k["active_employees"] == 3
    assert a["distribution"] == {"1": 1, "2": 0, "3": 1, "4": 1, "5": 1}
    assert [(t["date"], t["avg"], t["count"]) for t in a["trend"]] == [("2026-11-09", 4.0, 1), ("2026-11-10", 3.0, 3)]
    by = {d["name"].lower(): d for d in a["dishes"]}
    # "Mastava" ikki kun (nomi harf katta-kichikligidan qat'i nazar birlashadi): (5+2+3)/3
    assert by["mastava"]["count"] == 3 and by["mastava"]["days"] == 2 and by["mastava"]["avg"] == 3.33
    assert a["dishes"][0]["name"] == "Lag'mon" and a["dishes"][0]["avg"] == 5.0
    assert (await boss.get(f"{C}/analytics", params={"start": "2025-01-01", "end": TODAY})).status_code == 400
    assert (await hr.get("/api/v1/audit", params={"action": "canteen.reply"})).json()["total"] == 1
