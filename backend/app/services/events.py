"""Persisting counting / zone events and keeping the hourly roll-up in sync."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..models import Camera, TrafficSummary, VehicleEvent, ZoneEvent
from ..utils.timeutil import floor_hour_local, now_utc


def record_vehicle_event(db: Session, *, camera: Camera, line_id: int | None, track_id: int, vehicle_type: str,
                         direction: str, confidence: float, frame_number: int | None = None,
                         timestamp: datetime | None = None) -> VehicleEvent:
    ts = timestamp or now_utc()
    conf = min(max(float(confidence), 0.0), 1.0)
    ev = VehicleEvent(camera_id=camera.id, area_id=camera.area_id, line_id=line_id, track_id=track_id,
                      vehicle_type=vehicle_type, direction=direction, confidence=conf, timestamp=ts,
                      frame_number=frame_number)
    db.add(ev)
    stmt = pg_insert(TrafficSummary).values(
        camera_id=camera.id, area_id=camera.area_id, bucket_start=floor_hour_local(ts),
        vehicle_type=vehicle_type, direction=direction, vehicle_count=1,
    ).on_conflict_do_update(
        constraint="uq_summary",
        set_={"vehicle_count": TrafficSummary.vehicle_count + 1},
    )
    db.execute(stmt)
    db.commit()  # event + roll-up are committed together
    db.refresh(ev)
    return ev


def record_zone_event(db: Session, *, camera: Camera, zone_id: int, track_id: int, vehicle_type: str,
                      event_type: str, frame_number: int | None = None, timestamp: datetime | None = None) -> ZoneEvent:
    ev = ZoneEvent(zone_id=zone_id, camera_id=camera.id, area_id=camera.area_id, track_id=track_id,
                   vehicle_type=vehicle_type, event_type=event_type, timestamp=timestamp or now_utc(),
                   frame_number=frame_number)
    db.add(ev)
    db.commit()
    return ev


def rebuild_summaries(db: Session) -> int:
    """Recompute traffic_summaries from vehicle_events (repair tool; also used by tests)."""
    from ..config import get_settings
    tzname = get_settings().app_timezone
    db.query(TrafficSummary).delete()
    bucket = func.date_trunc("hour", func.timezone(tzname, VehicleEvent.timestamp))
    rows = db.execute(
        select(VehicleEvent.camera_id, VehicleEvent.area_id, bucket.label("b"), VehicleEvent.vehicle_type,
               VehicleEvent.direction, func.count().label("n"))
        .group_by(VehicleEvent.camera_id, VehicleEvent.area_id, bucket, VehicleEvent.vehicle_type,
                  VehicleEvent.direction)
    ).all()
    from ..utils.timeutil import tz
    for cam, area, b, vt, d, n in rows:
        db.add(TrafficSummary(camera_id=cam, area_id=area, bucket_start=b.replace(tzinfo=tz()),
                              vehicle_type=vt, direction=d, vehicle_count=n))
    db.commit()
    return len(rows)
