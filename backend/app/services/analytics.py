"""All traffic analytics. Everything is computed from PostgreSQL (traffic_summaries / vehicle_events);
nothing here is hard-coded or mocked."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, extract, func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Area, Camera, TrafficSummary as S, VehicleEvent
from ..utils.timeutil import floor_hour_local, now_utc, start_of_today, tz
from .status import level_from_count

CORE_TYPES = ["car", "motorcycle", "bus", "truck"]


@dataclass
class Filters:
    start: datetime | None = None
    end: datetime | None = None
    camera_id: int | None = None
    area_id: int | None = None
    vehicle_type: str | None = None
    direction: str | None = None


def _local(col):
    return func.timezone(get_settings().app_timezone, col)


def _where(f: Filters):
    conds = []
    if f.start:
        conds.append(S.bucket_start >= floor_hour_local(f.start))
    if f.end:
        conds.append(S.bucket_start < f.end)
    if f.camera_id:
        conds.append(S.camera_id == f.camera_id)
    if f.area_id:
        conds.append(S.area_id == f.area_id)
    if f.vehicle_type:
        conds.append(S.vehicle_type == f.vehicle_type)
    if f.direction:
        conds.append(S.direction == f.direction)
    return and_(*conds) if conds else True


def _type_dict(rows) -> dict[str, int]:
    d = {t: 0 for t in CORE_TYPES}
    for vt, n in rows:
        d[vt] = d.get(vt, 0) + int(n or 0)
    return d


# ---------------------------------------------------------------- headline numbers
def today_summary(db: Session, f: Filters | None = None) -> dict:
    f = f or Filters()
    t0 = start_of_today()
    today = Filters(start=t0, end=now_utc() + timedelta(hours=1), camera_id=f.camera_id, area_id=f.area_id)
    rows = db.execute(select(S.vehicle_type, func.sum(S.vehicle_count)).where(_where(today)).group_by(S.vehicle_type)).all()
    by_type = _type_dict(rows)
    total = sum(by_type.values())
    y = Filters(start=t0 - timedelta(days=1), end=t0, camera_id=f.camera_id, area_id=f.area_id)
    y_total = db.scalar(select(func.coalesce(func.sum(S.vehicle_count), 0)).where(_where(y))) or 0
    return {"date": t0.date().isoformat(), "total": total, "by_type": by_type,
            "yesterday_total": int(y_total),
            "change_vs_yesterday_pct": round((total - y_total) / y_total * 100, 1) if y_total else None}


def by_type(db: Session, f: Filters) -> list[dict]:
    rows = db.execute(select(S.vehicle_type, func.sum(S.vehicle_count)).where(_where(f))
                      .group_by(S.vehicle_type).order_by(func.sum(S.vehicle_count).desc())).all()
    total = sum(int(n) for _, n in rows) or 1
    return [{"vehicle_type": vt, "count": int(n), "share_pct": round(int(n) / total * 100, 1)} for vt, n in rows]


def by_direction(db: Session, f: Filters) -> list[dict]:
    rows = db.execute(select(S.direction, func.sum(S.vehicle_count)).where(_where(f))
                      .group_by(S.direction).order_by(func.sum(S.vehicle_count).desc())).all()
    return [{"direction": d, "count": int(n)} for d, n in rows]


def by_area(db: Session, f: Filters) -> list[dict]:
    rows = db.execute(
        select(Area.id, Area.name, S.vehicle_type, func.sum(S.vehicle_count))
        .join(Area, Area.id == S.area_id).where(_where(f)).group_by(Area.id, Area.name, S.vehicle_type)).all()
    out: dict[int, dict] = {}
    for aid, name, vt, n in rows:
        a = out.setdefault(aid, {"area_id": aid, "area_name": name, "total": 0, **{t: 0 for t in CORE_TYPES}})
        a[vt] = a.get(vt, 0) + int(n)
        a["total"] += int(n)
    return sorted(out.values(), key=lambda a: -a["total"])


def by_camera(db: Session, f: Filters) -> list[dict]:
    rows = db.execute(
        select(Camera.id, Camera.name, Area.name, S.vehicle_type, func.sum(S.vehicle_count))
        .join(Camera, Camera.id == S.camera_id).outerjoin(Area, Area.id == Camera.area_id)
        .where(_where(f)).group_by(Camera.id, Camera.name, Area.name, S.vehicle_type)).all()
    out: dict[int, dict] = {}
    for cid, cname, aname, vt, n in rows:
        c = out.setdefault(cid, {"camera_id": cid, "camera_name": cname, "area_name": aname, "total": 0,
                                 **{t: 0 for t in CORE_TYPES}})
        c[vt] = c.get(vt, 0) + int(n)
        c["total"] += int(n)
    return sorted(out.values(), key=lambda c: -c["total"])


# ---------------------------------------------------------------- time series
def _fill(points: dict[datetime, dict], start: datetime, end: datetime, step: timedelta, label_fmt: str) -> list[dict]:
    out, cur = [], start
    while cur < end:
        p = points.get(cur.replace(tzinfo=None), {})
        out.append({"bucket": cur.isoformat(), "label": cur.strftime(label_fmt), "count": p.get("count", 0),
                    **{t: p.get(t, 0) for t in CORE_TYPES}})
        cur += step
    return out


def _series(db: Session, f: Filters, trunc: str) -> dict[datetime, dict]:
    b = func.date_trunc(trunc, _local(S.bucket_start))
    rows = db.execute(select(b, S.vehicle_type, func.sum(S.vehicle_count)).where(_where(f))
                      .group_by(b, S.vehicle_type)).all()
    pts: dict[datetime, dict] = {}
    for ts, vt, n in rows:
        p = pts.setdefault(ts, {"count": 0})
        p[vt] = p.get(vt, 0) + int(n)
        p["count"] += int(n)
    return pts


def hourly(db: Session, f: Filters, hours: int | None = None) -> list[dict]:
    zone = tz()
    end = f.end or (now_utc().astimezone(zone) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    start = f.start or start_of_today()
    if hours:
        start = end - timedelta(hours=hours)
    start = start.astimezone(zone).replace(minute=0, second=0, microsecond=0)
    if (end - start) > timedelta(days=14):
        start = end - timedelta(days=14)
    ff = Filters(start, end, f.camera_id, f.area_id, f.vehicle_type, f.direction)
    return _fill(_series(db, ff, "hour"), start, end, timedelta(hours=1), "%H:%M")


def daily(db: Session, f: Filters, days: int = 14) -> list[dict]:
    zone = tz()
    today = start_of_today()
    start = (f.start.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
             if f.start else today - timedelta(days=days - 1))
    end = f.end or today + timedelta(days=1)
    if (end - start).days > 366:
        start = end - timedelta(days=366)
    ff = Filters(start, end, f.camera_id, f.area_id, f.vehicle_type, f.direction)
    pts = _series(db, ff, "day")
    out, cur = [], start
    while cur < end:
        p = pts.get(cur.replace(tzinfo=None), {})
        out.append({"bucket": cur.date().isoformat(), "label": cur.strftime("%a %d %b"), "count": p.get("count", 0),
                    **{t: p.get(t, 0) for t in CORE_TYPES}})
        cur += timedelta(days=1)
    return out


def weekly(db: Session, f: Filters, weeks: int = 8) -> list[dict]:
    today = start_of_today()
    this_monday = today - timedelta(days=today.weekday())
    start = this_monday - timedelta(weeks=weeks - 1)
    ff = Filters(start, this_monday + timedelta(weeks=1), f.camera_id, f.area_id, f.vehicle_type, f.direction)
    pts = _series(db, ff, "week")
    return _fill(pts, start, this_monday + timedelta(weeks=1), timedelta(weeks=1), "Wk %d %b")


def monthly(db: Session, f: Filters, months: int = 12) -> list[dict]:
    today = start_of_today().replace(day=1)
    starts = []
    cur = today
    for _ in range(months):
        starts.append(cur)
        cur = (cur - timedelta(days=1)).replace(day=1)
    starts.reverse()
    nxt = (today + timedelta(days=32)).replace(day=1)
    ff = Filters(starts[0], nxt, f.camera_id, f.area_id, f.vehicle_type, f.direction)
    pts = _series(db, ff, "month")
    return [{"bucket": s.date().isoformat(), "label": s.strftime("%b %Y"), "count": pts.get(s.replace(tzinfo=None), {}).get("count", 0),
             **{t: pts.get(s.replace(tzinfo=None), {}).get(t, 0) for t in CORE_TYPES}} for s in starts]


# ---------------------------------------------------------------- peaks & trends
def peak_hours(db: Session, f: Filters) -> dict:
    """Average vehicles per hour-of-day over the selected range (default: last 30 days)."""
    if not f.start:
        f = Filters(start_of_today() - timedelta(days=29), f.end, f.camera_id, f.area_id, f.vehicle_type, f.direction)
    hr = extract("hour", _local(S.bucket_start))
    day = func.date_trunc("day", _local(S.bucket_start))
    rows = db.execute(select(hr, func.sum(S.vehicle_count), func.count(func.distinct(day))).where(_where(f))
                      .group_by(hr)).all()
    by_hour = {int(h): (int(n), int(d)) for h, n, d in rows}
    hours = [{"hour": h, "label": f"{h:02d}:00", "total": by_hour.get(h, (0, 0))[0],
              "avg_per_day": round(by_hour[h][0] / by_hour[h][1], 1) if h in by_hour else 0.0} for h in range(24)]
    top = sorted([h for h in hours if h["total"] > 0], key=lambda h: -h["avg_per_day"])[:3]
    return {"hours": hours, "peak_hours": top}


def trends(db: Session, f: Filters) -> dict:
    t0 = start_of_today()
    cur = Filters(t0 - timedelta(days=6), t0 + timedelta(days=1), f.camera_id, f.area_id)
    prev = Filters(t0 - timedelta(days=13), t0 - timedelta(days=6), f.camera_id, f.area_id)
    q = lambda ff: int(db.scalar(select(func.coalesce(func.sum(S.vehicle_count), 0)).where(_where(ff))) or 0)  # noqa: E731
    c, p = q(cur), q(prev)
    pct = round((c - p) / p * 100, 1) if p else None
    direction = "no_baseline" if pct is None else ("up" if pct > 2 else "down" if pct < -2 else "stable")
    return {"last_7_days": c, "previous_7_days": p, "change_pct": pct, "direction": direction}


# ---------------------------------------------------------------- live level for map / cameras
def live_levels(db: Session, processing_ids: set[int]) -> list[dict]:
    """Per-camera vehicles today + current traffic level (last-15-minute rate extrapolated to /hour)."""
    since = now_utc() - timedelta(minutes=15)
    recent = dict(db.execute(select(VehicleEvent.camera_id, func.count()).where(VehicleEvent.timestamp >= since)
                             .group_by(VehicleEvent.camera_id)).all())
    today = dict(db.execute(select(S.camera_id, func.sum(S.vehicle_count))
                            .where(_where(Filters(start_of_today(), now_utc() + timedelta(hours=1))))
                            .group_by(S.camera_id)).all())
    out = []
    for cam in db.scalars(select(Camera).order_by(Camera.id)).all():
        cap = cam.area.hourly_capacity if cam.area else 1200
        n15 = int(recent.get(cam.id, 0))
        live = cam.id in processing_ids
        level = "NO_DATA" if (n15 == 0 and not live) else level_from_count(n15 * 4, cap)
        lat = cam.latitude if cam.latitude is not None else (cam.area.latitude if cam.area else None)
        lng = cam.longitude if cam.longitude is not None else (cam.area.longitude if cam.area else None)
        out.append({"camera_id": cam.id, "camera_name": cam.name, "area_id": cam.area_id,
                    "area_name": cam.area.name if cam.area else None, "status": cam.status, "processing": live,
                    "latitude": lat, "longitude": lng, "vehicles_today": int(today.get(cam.id, 0) or 0),
                    "vehicles_last_15_min": n15, "estimated_per_hour": n15 * 4, "hourly_capacity": cap,
                    "traffic_level": level})
    return out
