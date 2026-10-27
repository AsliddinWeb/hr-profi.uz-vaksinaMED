"""Davomat dashboardi: hamma raqam tabel bilan BIR manbadan (`_rows` + `day_status`) hisoblanadi."""

from collections import defaultdict
from datetime import date
from typing import Any

from app.models.employees import Employee

ATTENDED = {"present", "late", "early", "late_early", "working", "no_checkout", "incomplete", "unscheduled"}
LATE = {"late", "late_early"}
EARLY = {"early", "late_early"}


def rate(attended: int, absent: int) -> float | None:
    """Davomat foizi: kelganlar / (kelganlar + kelmaganlar). Kutilayotgan va kelgusi kunlar hisobga olinmaydi."""
    total = attended + absent
    return round(attended / total, 4) if total else None


class Bucket:
    __slots__ = ("absent", "attended", "early", "employees", "late", "late_minutes", "worked")

    def __init__(self) -> None:
        self.employees = self.attended = self.absent = self.late = self.early = 0
        self.late_minutes = self.worked = 0

    def out(self, **extra: Any) -> dict[str, Any]:
        return {
            **extra,
            "employees": self.employees,
            "attended": self.attended,
            "absent": self.absent,
            "late_count": self.late,
            "late_minutes": self.late_minutes,
            "rate": rate(self.attended, self.absent),
        }


def aggregate(
    employees: list[Employee],
    rows: dict[int, list[dict[str, Any]]],
    start: date,
    end: date,
    depts: dict[int, str],
    branches: dict[int, str],
    top: int = 10,
) -> dict[str, Any]:
    total = Bucket()
    by_dept: dict[int | None, Bucket] = defaultdict(Bucket)
    by_branch: dict[int | None, Bucket] = defaultdict(Bucket)
    trend: dict[date, dict[str, int]] = {}
    statuses: dict[str, int] = defaultdict(int)
    people: list[dict[str, Any]] = []
    on_time = 0

    for e in employees:
        mine = Bucket()
        for d in rows[e.id]:
            st, rec = d["status"], d["record"]
            statuses[st] += 1
            day = trend.setdefault(d["date"], {"attended": 0, "late": 0, "absent": 0})
            if st in ATTENDED:
                mine.attended += 1
                day["attended"] += 1
                if st not in LATE:
                    on_time += 1
            if st == "absent":
                mine.absent += 1
                day["absent"] += 1
            if st in LATE:
                day["late"] += 1
            if rec is not None:
                mine.late += 1 if rec.late_minutes else 0
                mine.early += 1 if rec.early_leave_minutes else 0
                mine.late_minutes += rec.late_minutes
                mine.worked += rec.worked_minutes
        mine.employees = 1
        for bucket in (total, by_dept[e.department_id], by_branch[e.branch_id]):
            bucket.employees += 1
            bucket.attended += mine.attended
            bucket.absent += mine.absent
            bucket.late += mine.late
            bucket.early += mine.early
            bucket.late_minutes += mine.late_minutes
            bucket.worked += mine.worked
        people.append({"employee": {"id": e.id, "full_name": e.full_name}, "late_count": mine.late,
                       "late_minutes": mine.late_minutes, "absent": mine.absent, "attended": mine.attended})  # fmt: skip

    def groups(src: dict[int | None, Bucket], names: dict[int, str]) -> list[dict[str, Any]]:
        out = [b.out(id=k, name=names.get(k) if k is not None else None) for k, b in src.items()]
        return sorted(out, key=lambda r: (r["rate"] is None, r["rate"] or 0, r["name"] or ""))

    kpis = total.out()
    kpis |= {
        "early_count": total.early,
        "worked_minutes": total.worked,
        "punctuality": round(on_time / total.attended, 4) if total.attended else None,
        "no_checkout": statuses.get("no_checkout", 0),
        "scheduled_days": total.attended + total.absent + statuses.get("pending", 0) + statuses.get("future", 0),
    }
    return {
        "start": start,
        "end": end,
        "kpis": kpis,
        "statuses": dict(statuses),
        "trend": [{"date": d, **v, "rate": rate(v["attended"], v["absent"])} for d, v in sorted(trend.items())],
        "by_department": groups(by_dept, depts),
        "by_branch": groups(by_branch, branches),
        "top_late": sorted((p for p in people if p["late_count"]), key=lambda p: (-p["late_count"], -p["late_minutes"]))[:top],
        "top_absent": sorted((p for p in people if p["absent"]), key=lambda p: -p["absent"])[:top],
    }
