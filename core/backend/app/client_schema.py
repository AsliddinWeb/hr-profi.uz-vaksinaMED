"""client.yaml sxemasi va mijoz papkasini tekshirish (`python -m app.cli validate-client <papka>`).

Ishga tushishda ham chaqiriladi: xatolar logga yoziladi (ilova baribir standart sozlamalar bilan ishlaydi),
`new-client.sh` va `make validate-client` esa xatoda to'xtaydi.
"""

import ast
import re
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from app.modules import CORE_MODULES
from app.plans import PLAN_MODULES

NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,30}$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
TOP_KEYS = {"name", "brand", "modules", "settings", "plan", "license"}
LICENSE_KEYS = {"seats", "valid_until", "holder"}
BRAND_KEYS = {"name", "tagline", "primary", "accent", "logo"}
KNOWN_SETTINGS = {"timezone", "map"}


def json_schema() -> dict[str, Any]:
    """Muharrir (VS Code YAML) va hujjat uchun JSON Schema."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "HR-Profi client.yaml",
        "type": "object",
        "additionalProperties": False,
        "required": ["name"],
        "properties": {
            "name": {"type": "string", "pattern": NAME_RE.pattern, "description": "Mijoz kaliti: papka nomi (clients/<name>) va CLIENT_NAME bilan bir xil"},
            "brand": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 60},
                    "tagline": {"type": "string", "maxLength": 120},
                    "primary": {"type": "string", "pattern": HEX_RE.pattern},
                    "accent": {"type": "string", "pattern": HEX_RE.pattern},
                    "logo": {"type": ["string", "null"], "description": "Logotip yo'li (frontend_ext/public ichida yoki to'liq URL)"},
                },
            },
            "plan": {"enum": sorted(PLAN_MODULES), "description": "KOSHI tarifi: modullar tarif bo'yicha yoqiladi. Berilmasa cheklov yo'q"},
            "license": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "seats": {"type": "integer", "minimum": 1, "description": "Faol foydalanuvchilar soni chegarasi"},
                    "valid_until": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$", "description": "Litsenziya amal qilish sanasi (YYYY-MM-DD)"},
                    "holder": {"type": "string", "maxLength": 120},
                },
            },
            "modules": {"type": "object", "additionalProperties": False, "properties": {k: {"type": "boolean"} for k in sorted(CORE_MODULES)}},
            "settings": {
                "type": "object",
                "description": "Core quyidagilarni o'qiydi; qolganini mijoz extension kodi ishlatadi",
                "properties": {
                    "timezone": {"type": "string", "examples": ["Asia/Tashkent"]},
                    "map": {"type": "object", "properties": {"tiles": {"type": "string", "description": "{z}/{x}/{y} li URL shabloni"}, "attribution": {"type": "string"}}},
                },
            },
        },
    }


def _check_brand(brand: Any, base: Path, errors: list[str], warnings: list[str]) -> None:
    if not isinstance(brand, dict):
        errors.append("brand: mapping bo'lishi kerak")
        return
    for k in brand:
        if k not in BRAND_KEYS:
            errors.append(f"brand.{k}: noma'lum kalit (ruxsat: {', '.join(sorted(BRAND_KEYS))})")
    name = brand.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip() or len(name) > 60):
        errors.append("brand.name: 1–60 belgili matn bo'lishi kerak")
    for k in ("primary", "accent"):
        v = brand.get(k)
        if v is not None and not (isinstance(v, str) and HEX_RE.match(v)):
            errors.append(f"brand.{k}: '#rrggbb' ko'rinishidagi rang bo'lishi kerak (hozir: {v!r})")
    logo = brand.get("logo")
    if isinstance(logo, str) and logo and not logo.startswith(("http://", "https://", "/")) and not (base / "frontend_ext" / "public" / logo).exists():
        warnings.append(f"brand.logo: '{logo}' fayli frontend_ext/public ichida topilmadi")


def validate_client_dir(path: str | Path) -> tuple[list[str], list[str]]:
    """(xatolar, ogohlantirishlar). Xato bo'lsa mijoz papkasi yaroqsiz."""
    base = Path(path)
    errors: list[str] = []
    warnings: list[str] = []
    cfg_path = base / "client.yaml"
    if not base.is_dir():
        return [f"{base}: papka topilmadi"], warnings
    if not cfg_path.is_file():
        return [f"{cfg_path}: fayl yo'q"], warnings
    try:
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        return [f"client.yaml: YAML xatosi: {e}"], warnings
    if not isinstance(raw, dict):
        return ["client.yaml: ildiz mapping bo'lishi kerak"], warnings

    for k in raw:
        if k not in TOP_KEYS:
            errors.append(f"{k}: noma'lum yuqori daraja kalit (ruxsat: {', '.join(sorted(TOP_KEYS))})")
    name = raw.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        errors.append("name: kichik lotin harf/raqam/'-'/'_' (2–31 belgi), harf bilan boshlanishi kerak")
    elif name != base.name:
        warnings.append(f"name '{name}' papka nomi '{base.name}' bilan mos emas (CLIENT_NAME ni tekshiring)")
    if "brand" in raw:
        _check_brand(raw["brand"], base, errors, warnings)
    plan = raw.get("plan")
    if plan is not None and plan not in PLAN_MODULES:
        errors.append(f"plan: {', '.join(sorted(PLAN_MODULES))} dan biri bo'lishi kerak (hozir: {plan!r})")
    lic = raw.get("license")
    if lic is not None:
        if not isinstance(lic, dict):
            errors.append("license: mapping bo'lishi kerak")
        else:
            for k in lic:
                if k not in LICENSE_KEYS:
                    errors.append(f"license.{k}: noma'lum kalit (ruxsat: {', '.join(sorted(LICENSE_KEYS))})")
            seats = lic.get("seats")
            if seats is not None and not (isinstance(seats, int) and not isinstance(seats, bool) and seats >= 1):
                errors.append("license.seats: 1 dan katta butun son bo'lishi kerak")
            until = lic.get("valid_until")
            if until is not None:
                try:
                    from datetime import date as _date  # noqa: PLC0415

                    _date.fromisoformat(str(until))
                except ValueError:
                    errors.append(f"license.valid_until: YYYY-MM-DD bo'lishi kerak (hozir: {until!r})")
            if plan is None:
                warnings.append("license berilgan, lekin plan yo'q: tarif cheklovlari qo'llanmaydi")
    mods = raw.get("modules")
    if mods is not None:
        if not isinstance(mods, dict):
            errors.append("modules: mapping bo'lishi kerak")
        else:
            for k, v in mods.items():
                if k not in CORE_MODULES:
                    errors.append(f"modules.{k}: noma'lum modul (ro'yxat: core/backend/app/modules.py)")
                elif not isinstance(v, bool):
                    errors.append(f"modules.{k}: true yoki false bo'lishi kerak")
            if mods.get("dashboard") is False:
                warnings.append("modules.dashboard o'chirilgan: bosh sahifa bo'sh qoladi")
    st = raw.get("settings")
    if st is not None:
        if not isinstance(st, dict):
            errors.append("settings: mapping bo'lishi kerak")
        else:
            tzname = st.get("timezone")
            if tzname is not None:
                try:
                    ZoneInfo(str(tzname))
                except Exception:  # noqa: BLE001
                    errors.append(f"settings.timezone: noma'lum vaqt mintaqasi {tzname!r}")
            m = st.get("map")
            if m is not None:
                if not isinstance(m, dict) or "tiles" not in m:
                    errors.append("settings.map: {tiles: <url>, attribution: <matn>} bo'lishi kerak")
                elif not all(t in str(m["tiles"]) for t in ("{z}", "{x}", "{y}")):
                    errors.append("settings.map.tiles: {z}/{x}/{y} bo'lishi kerak")
            extra = sorted(k for k in st if k not in KNOWN_SETTINGS)
            if extra:
                warnings.append(f"settings: core o'qimaydigan kalitlar (extension uchun bo'lsa — normal): {', '.join(extra)}")

    backend = base / "backend_ext" / "__init__.py"
    if backend.is_file():
        try:
            tree = ast.parse(backend.read_text(encoding="utf-8"))
            funcs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if "setup" not in funcs:
                warnings.append("backend_ext/__init__.py: setup(ctx) funksiyasi yo'q: extension yuklanmaydi")
        except SyntaxError as e:
            errors.append(f"backend_ext/__init__.py: sintaksis xatosi (qator {e.lineno})")
    front = base / "frontend_ext" / "index.tsx"
    if front.is_file() and "export default" not in front.read_text(encoding="utf-8"):
        errors.append("frontend_ext/index.tsx: `export default function register(api)` bo'lishi kerak")
    versions = base / "migrations" / "versions"
    if versions.is_dir() and any(versions.glob("*.py")) and not (base / "migrations" / "env.py").is_file():
        errors.append("migrations/versions bor, lekin migrations/env.py yo'q")
    for f in sorted(versions.glob("*.py")) if versions.is_dir() else []:
        text = f.read_text(encoding="utf-8")
        m = re.search(r'^revision\s*=\s*["\']([^"\']+)["\']', text, re.M)
        if not m or not m.group(1).startswith("ext"):
            warnings.append(f"migrations/versions/{f.name}: revision 'ext' bilan boshlanishi tavsiya etiladi (core bilan chalkashmasligi uchun)")
        if "op.create_table(" in text and not re.search(r'create_table\(\s*["\']client_', text):
            warnings.append(f"migrations/versions/{f.name}: jadval nomi 'client_' bilan boshlanishi kerak (core jadvallari bilan to'qnashmaslik uchun)")
    return errors, warnings
