from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..services import analytics as an
from ..services.processing_manager import processing
from .deps import filters

router = APIRouter(prefix="/traffic", tags=["traffic"])


@router.get("/today")
def today(f: an.Filters = Depends(filters), db: Session = Depends(get_db)):
    return an.today_summary(db, f)


@router.get("/hourly")
def hourly(hours: int | None = Query(None, ge=1, le=336), f: an.Filters = Depends(filters), db: Session = Depends(get_db)):
    return an.hourly(db, f, hours)


@router.get("/daily")
def daily(days: int = Query(14, ge=1, le=366), f: an.Filters = Depends(filters), db: Session = Depends(get_db)):
    return an.daily(db, f, days)


@router.get("/weekly")
def weekly(weeks: int = Query(8, ge=1, le=52), f: an.Filters = Depends(filters), db: Session = Depends(get_db)):
    return an.weekly(db, f, weeks)


@router.get("/monthly")
def monthly(months: int = Query(12, ge=1, le=36), f: an.Filters = Depends(filters), db: Session = Depends(get_db)):
    return an.monthly(db, f, months)


@router.get("/by-area")
def by_area(f: an.Filters = Depends(filters), db: Session = Depends(get_db)):
    return an.by_area(db, f)


@router.get("/by-camera")
def by_camera(f: an.Filters = Depends(filters), db: Session = Depends(get_db)):
    return an.by_camera(db, f)


@router.get("/by-type")
def by_type(f: an.Filters = Depends(filters), db: Session = Depends(get_db)):
    return an.by_type(db, f)


@router.get("/by-direction")
def by_direction(f: an.Filters = Depends(filters), db: Session = Depends(get_db)):
    return an.by_direction(db, f)


@router.get("/peak-hours")
def peak_hours(f: an.Filters = Depends(filters), db: Session = Depends(get_db)):
    return an.peak_hours(db, f)


@router.get("/trends")
def trends(f: an.Filters = Depends(filters), db: Session = Depends(get_db)):
    return an.trends(db, f)


@router.get("/map")
def map_overview(db: Session = Depends(get_db)):
    return an.live_levels(db, processing.running_ids())
