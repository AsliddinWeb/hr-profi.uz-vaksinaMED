import textwrap
from datetime import date

import pytest

from app.client_schema import json_schema, validate_client_dir
from app.modules import CORE_MODULES
from tests.conftest import login, make_user


def write(tmp_path, name, yaml_text, files=None):
    base = tmp_path / name
    base.mkdir()
    (base / "client.yaml").write_text(textwrap.dedent(yaml_text))
    for rel, text in (files or {}).items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(text))
    return base


def test_valid_minimal_and_full(tmp_path):
    base = write(tmp_path, "acme", "name: acme\n")
    assert validate_client_dir(base) == ([], [])
    base = write(
        tmp_path, "full", """
        name: full
        brand: {name: Full HR, tagline: x, primary: "#112233", accent: "#ABCDEF"}
        modules: {logistics: false, calls: true}
        settings: {timezone: Asia/Tashkent, map: {tiles: "https://t/{z}/{x}/{y}.png", attribution: OSM}, custom_rule: 5}
        """,
        files={"backend_ext/__init__.py": "def setup(ctx):\n    pass\n", "frontend_ext/index.tsx": "export default function register(api) {}\n"},
    )
    errors, warnings = validate_client_dir(base)
    assert errors == [] and any("custom_rule" in w for w in warnings)


@pytest.mark.parametrize(
    ("yaml_text", "fragment"),
    [
        ("name: Bad Name\n", "name:"),
        ("name: x1\nfoo: 1\n", "foo"),
        ("name: x1\nbrand: {primary: red}\n", "brand.primary"),
        ("name: x1\nbrand: {colour: red}\n", "brand.colour"),
        ("name: x1\nmodules: {nonsense: true}\n", "modules.nonsense"),
        ("name: x1\nmodules: {calls: yes please}\n", "modules.calls"),
        ("name: x1\nsettings: {timezone: Mars/Base}\n", "timezone"),
        ("name: x1\nsettings: {map: {tiles: 'http://x/tiles.png'}}\n", "settings.map.tiles"),
        ("- just\n- a list\n", "mapping"),
        (": : :\n- [", "YAML"),
    ],
)
def test_invalid_configs_are_reported(tmp_path, yaml_text, fragment):
    base = tmp_path / "x1"
    base.mkdir()
    (base / "client.yaml").write_text(yaml_text)
    errors, _ = validate_client_dir(base)
    assert any(fragment in e for e in errors), errors


def test_missing_dir_and_file(tmp_path):
    assert "topilmadi" in validate_client_dir(tmp_path / "nope")[0][0]
    (tmp_path / "empty").mkdir()
    assert "yo'q" in validate_client_dir(tmp_path / "empty")[0][0]


def test_extension_structure_checks(tmp_path):
    base = write(
        tmp_path, "ext1", "name: ext1\n",
        files={
            "backend_ext/__init__.py": "def helper():\n    pass\n",
            "frontend_ext/index.tsx": "const x = 1\n",
            "migrations/versions/0001_a.py": "revision = 'abc'\ndown_revision = None\nimport sqlalchemy as sa\nfrom alembic import op\ndef upgrade():\n    op.create_table('notes', sa.Column('id', sa.Integer))\n",
        },
    )
    errors, warnings = validate_client_dir(base)
    assert any("export default" in e for e in errors) and any("env.py" in e for e in errors)
    assert any("setup(ctx)" in w for w in warnings) and any("'ext'" in w for w in warnings) and any("client_" in w for w in warnings)
    broken = write(tmp_path, "ext2", "name: ext2\n", files={"backend_ext/__init__.py": "def setup(:\n"})
    assert any("sintaksis" in e for e in validate_client_dir(broken)[0])
    name_mismatch = write(tmp_path, "dir1", "name: other\n")
    assert any("mos emas" in w for w in validate_client_dir(name_mismatch)[1])


def test_json_schema_covers_modules():
    s = json_schema()
    assert set(s["properties"]["modules"]["properties"]) == set(CORE_MODULES)
    assert s["required"] == ["name"] and s["additionalProperties"] is False


@pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")
async def test_core_emits_events_for_extensions(new_client, app):
    seen = []
    app.state.events.on("ticket.created", lambda **kw: seen.append(("ticket", kw["number"], kw["priority"])))
    app.state.events.on("employee.created", lambda **kw: seen.append(("employee", kw["full_name"])))
    app.state.events.on("employee.dismissed", lambda **kw: seen.append(("dismissed", kw["employee_id"])))
    await make_user("hr", "hr_direktor")
    c = new_client()
    assert (await login(c, "hr")).status_code == 200
    r = await c.post("/api/v1/helpdesk", json={"title": "Printer ishlamayapti", "priority": "high"})
    assert r.status_code == 201
    assert seen == [("ticket", "T-2026-0001", "high")] or seen[0][0] == "ticket"
    r = await c.post("/api/v1/employees", json={"last_name": "Karimov", "first_name": "Aziz"})
    assert r.status_code == 201, r.text
    emp_id = r.json()["employee"]["id"]
    assert ("employee", "Karimov Aziz") in seen
    r = await c.post(f"/api/v1/employees/{emp_id}/dismiss", json={"date": date.today().isoformat(), "reason": "own_will"})
    assert r.status_code == 200, r.text
    assert ("dismissed", emp_id) in seen
