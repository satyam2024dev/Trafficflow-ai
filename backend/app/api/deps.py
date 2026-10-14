from __future__ import annotations

from datetime import date

from fastapi import HTTPException, Query

from ..services.analytics import Filters
from ..utils.timeutil import end_of_day_exclusive, start_of_day


def filters(
    start_date: date | None = Query(None, description="Inclusive start date (YYYY-MM-DD, app timezone)"),
    end_date: date | None = Query(None, description="Inclusive end date"),
    area_id: int | None = Query(None, gt=0),
    camera_id: int | None = Query(None, gt=0),
    vehicle_type: str | None = Query(None, max_length=30, pattern=r"^[A-Za-z_ -]+$"),
    direction: str | None = Query(None, max_length=40),
) -> Filters:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "start_date must be on or before end_date")
    return Filters(
        start=start_of_day(start_date) if start_date else None,
        end=end_of_day_exclusive(end_date) if end_date else None,
        area_id=area_id, camera_id=camera_id, vehicle_type=vehicle_type, direction=direction,
    )
