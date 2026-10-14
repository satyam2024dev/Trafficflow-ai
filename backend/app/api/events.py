from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..models import Area, Camera, VehicleEvent as E
from ..schemas.schemas import EventPage, VehicleEventOut
from ..services import analytics as an
from ..services.reports import events_csv
from .deps import filters

router = APIRouter(prefix="/events", tags=["events"])

SORTABLE = {
    "timestamp": E.timestamp, "camera": Camera.name, "area": Area.name, "vehicle_type": E.vehicle_type,
    "direction": E.direction, "confidence": E.confidence, "track_id": E.track_id, "id": E.id,
}


def _query(f: an.Filters, search: str | None):
    q = (select(E, Camera.name.label("camera_name"), Area.name.label("area_name"))
         .join(Camera, Camera.id == E.camera_id).outerjoin(Area, Area.id == E.area_id))
    if f.start: q = q.where(E.timestamp >= f.start)
    if f.end: q = q.where(E.timestamp < f.end)
    if f.camera_id: q = q.where(E.camera_id == f.camera_id)
    if f.area_id: q = q.where(E.area_id == f.area_id)
    if f.vehicle_type: q = q.where(E.vehicle_type == f.vehicle_type)
    if f.direction: q = q.where(E.direction == f.direction)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(E.vehicle_type.ilike(like), E.direction.ilike(like), Camera.name.ilike(like),
                        Area.name.ilike(like), cast(E.track_id, String).like(like)))
    return q


def _row(e, cam, area) -> dict:
    d = VehicleEventOut.model_validate(e).model_dump()
    d["camera_name"], d["area_name"] = cam, area
    return d


@router.get("", response_model=EventPage)
def list_events(
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
    sort_by: Literal["timestamp", "camera", "area", "vehicle_type", "direction", "confidence", "track_id", "id"] = "timestamp",
    order: Literal["asc", "desc"] = "desc", search: str | None = Query(None, max_length=60),
    f: an.Filters = Depends(filters), db: Session = Depends(get_db),
):
    base = _query(f, search)
    total = db.scalar(select(func.count()).select_from(base.order_by(None).subquery())) or 0
    col = SORTABLE[sort_by]
    base = base.order_by(col.asc() if order == "asc" else col.desc(), E.id.desc())
    rows = db.execute(base.limit(page_size).offset((page - 1) * page_size)).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_row(*r) for r in rows]}


@router.get("/export")
def export_events(search: str | None = Query(None, max_length=60), f: an.Filters = Depends(filters),
                  db: Session = Depends(get_db)):
    rows = db.execute(_query(f, search).order_by(E.timestamp.desc()).limit(100_000)).all()
    body = events_csv([_row(*r) for r in rows])
    return Response(body, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="trafficflow_events.csv"'})
