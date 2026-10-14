from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Area, Camera, VehicleEvent
from ..utils.timeutil import now_utc, start_of_today
from . import analytics as an


def build_report(db: Session, f: an.Filters) -> dict:
    if not f.start:
        f = an.Filters(start_of_today() - timedelta(days=6), f.end or start_of_today() + timedelta(days=1),
                       f.camera_id, f.area_id, f.vehicle_type, f.direction)
    if not f.end:
        f.end = start_of_today() + timedelta(days=1)
    types = an.by_type(db, f)
    total = sum(t["count"] for t in types)
    peaks = an.peak_hours(db, f)
    area_name = db.get(Area, f.area_id).name if f.area_id and db.get(Area, f.area_id) else "All areas"
    cam_name = db.get(Camera, f.camera_id).name if f.camera_id and db.get(Camera, f.camera_id) else "All cameras"
    return {
        "generated_at": now_utc().isoformat(),
        "range": {"start": f.start.isoformat(), "end": f.end.isoformat()},
        "area": area_name, "camera": cam_name,
        "total_vehicles": total, "by_type": types, "by_direction": an.by_direction(db, f),
        "by_area": an.by_area(db, f), "by_camera": an.by_camera(db, f),
        "peak_hours": peaks["peak_hours"], "daily": an.daily(db, f, days=31),
        "summary": (f"{total:,} vehicles counted between {f.start.date()} and {(f.end - timedelta(seconds=1)).date()} "
                    f"({area_name}, {cam_name})."),
    }


def report_csv(rep: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["TrafficFlow AI - Traffic Report"])
    w.writerow(["Generated", rep["generated_at"]])
    w.writerow(["Range start", rep["range"]["start"]])
    w.writerow(["Range end", rep["range"]["end"]])
    w.writerow(["Area", rep["area"]])
    w.writerow(["Camera", rep["camera"]])
    w.writerow(["Summary", rep["summary"]])
    w.writerow([])
    w.writerow(["Vehicle type distribution"]); w.writerow(["vehicle_type", "count", "share_pct"])
    for t in rep["by_type"]:
        w.writerow([t["vehicle_type"], t["count"], t["share_pct"]])
    w.writerow(["TOTAL", rep["total_vehicles"], ""])
    w.writerow([])
    w.writerow(["Direction"]); w.writerow(["direction", "count"])
    for d in rep["by_direction"]:
        w.writerow([d["direction"], d["count"]])
    w.writerow([])
    w.writerow(["By area"]); w.writerow(["area", "car", "motorcycle", "bus", "truck", "total"])
    for a in rep["by_area"]:
        w.writerow([a["area_name"], a.get("car", 0), a.get("motorcycle", 0), a.get("bus", 0), a.get("truck", 0), a["total"]])
    w.writerow([])
    w.writerow(["By camera"]); w.writerow(["camera", "area", "total"])
    for c in rep["by_camera"]:
        w.writerow([c["camera_name"], c["area_name"] or "", c["total"]])
    w.writerow([])
    w.writerow(["Peak hours (avg vehicles/day)"]); w.writerow(["hour", "avg_per_day", "total"])
    for h in rep["peak_hours"]:
        w.writerow([h["label"], h["avg_per_day"], h["total"]])
    w.writerow([])
    w.writerow(["Daily totals"]); w.writerow(["date", "total", "car", "motorcycle", "bus", "truck"])
    for d in rep["daily"]:
        w.writerow([d["bucket"], d["count"], d["car"], d["motorcycle"], d["bus"], d["truck"]])
    return out.getvalue()


def events_csv(rows: list) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "timestamp", "camera", "area", "track_id", "vehicle_type", "direction", "confidence", "frame_number"])
    for e in rows:
        w.writerow([e["id"], e["timestamp"], e["camera_name"], e["area_name"] or "", e["track_id"], e["vehicle_type"],
                    e["direction"], round(e["confidence"], 3), e["frame_number"] if e["frame_number"] is not None else ""])
    return out.getvalue()
