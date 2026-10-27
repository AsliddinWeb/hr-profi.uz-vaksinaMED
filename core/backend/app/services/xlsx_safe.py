"""Jadval (Excel/CSV) formula-injection himoyasi: bazadagi matn `=`, `+`, `-`, `@` bilan boshlansa Excel uni FORMULA sifatida bajarishi mumkin
(masalan xodim ismi `=HYPERLINK(...)`). Barcha eksportlarda yozishdan oldin `harden(wb)` chaqiriladi."""

import re
from typing import Any

from openpyxl.workbook import Workbook

TRIGGERS = ("=", "+", "-", "@", "\t", "\r")
# Bizning o'zimiz yozadigan yagona formulalar: jami qatori `=SUM(D2:D40)`
OWN_FORMULA = re.compile(r"^=SUM\([A-Z]{1,2}\d+:[A-Z]{1,2}\d+\)$")


def harden(wb: Workbook) -> Workbook:
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if isinstance(v, str) and v.startswith(TRIGGERS) and not OWN_FORMULA.match(v):
                    cell.data_type = "s"  # formula emas, matn
                    cell.quotePrefix = True  # Excel tahrirlashda ham formulaga aylantirmaydi
    return wb


def csv_safe(v: Any) -> Any:
    """CSV katak qiymati: xavfli boshlanishli matnga `'` qo'shiladi."""
    if isinstance(v, str) and v.startswith(TRIGGERS):
        return "'" + v
    return v
