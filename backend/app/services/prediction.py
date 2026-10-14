"""Simple, transparent traffic estimation from historical hourly counts.

Method (deliberately not a black box):
  1. Aggregate historical vehicles per local hour (optionally for one area).
  2. For each future hour, average past values for the same weekday+hour. If there are none, fall
     back to the same hour on any weekday, then to the average of the most recent hours.
  3. Convert to LOW / MODERATE / HIGH / CRITICAL using the area's configured hourly capacity.

This is an estimate - never a guarantee - and the response says how much data it was based on.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Area, TrafficSummary as S
from ..utils.timeutil import floor_hour_local, now_utc, tz
from .status import level_from_count

DISCLAIMER = ("These are statistical predictions based on past counts, not guaranteed facts. "
              "Accuracy improves as more days of real data are collected.")


def _history(db: Session, area_id: int | None) -> dict:
    """{local_hour_start(naive): total}, excluding the current (incomplete) hour."""
    b = func.date_trunc("hour", func.timezone(str(tz()), S.bucket_start))
    q = select(b, func.sum(S.vehicle_count)).group_by(b)
    if area_id:
        q = q.where(S.area_id == area_id)
    current = floor_hour_local(now_utc()).replace(tzinfo=None)
    return {ts: int(n) for ts, n in db.execute(q).all() if ts < current}


def predict(db: Session, area_id: int | None = None, hours_ahead: int = 6) -> dict:
    hours_ahead = max(1, min(hours_ahead, 24))
    if area_id:
        area = db.get(Area, area_id)
        capacity = area.hourly_capacity if area else 1200
        scope = area.name if area else f"area {area_id}"
    else:
        capacity = int(db.scalar(select(func.coalesce(func.sum(Area.hourly_capacity), 1200))) or 1200)
        scope = "all areas"

    hist = _history(db, area_id)
    base = {"scope": scope, "area_id": area_id, "hourly_capacity": capacity, "is_prediction": True,
            "disclaimer": DISCLAIMER, "history_hours": len(hist),
            "history_days": len({t.date() for t in hist})}
    if not hist:
        return {**base, "status": "insufficient_data", "predictions": [],
                "message": "No completed hours of traffic data yet. Run a video for at least one full clock hour "
                           "(or several days) to enable predictions."}

    recent = [v for _, v in sorted(hist.items())[-24:]]
    recent_avg = sum(recent) / len(recent)
    out = []
    start = floor_hour_local(now_utc()) + timedelta(hours=1)
    for i in range(hours_ahead):
        ts = start + timedelta(hours=i)
        same = [v for t, v in hist.items() if t.weekday() == ts.weekday() and t.hour == ts.hour]
        same_hour = [v for t, v in hist.items() if t.hour == ts.hour]
        if len(same) >= 2:
            est, basis, conf = sum(same) / len(same), f"avg of {len(same)} past {ts.strftime('%A')} {ts.hour:02d}:00 hours", "medium" if len(same) < 4 else "high"
        elif same:
            est, basis, conf = same[0], f"1 past {ts.strftime('%A')} {ts.hour:02d}:00 observation", "low"
        elif same_hour:
            est, basis, conf = sum(same_hour) / len(same_hour), f"avg of {len(same_hour)} past {ts.hour:02d}:00 hours (any weekday)", "low"
        else:
            est, basis, conf = recent_avg, f"average of the last {len(recent)} recorded hours", "low"
        est = round(est)
        out.append({"hour_start": ts.isoformat(), "label": f"{ts.hour:02d}:00 - {(ts.hour + 1) % 24:02d}:00",
                    "predicted_vehicles": est, "approx_text": f"approximately {est:,} vehicles",
                    "traffic_status": level_from_count(est, capacity), "confidence": conf, "basis": basis})
    return {**base, "status": "ok", "predictions": out, "message": None}
