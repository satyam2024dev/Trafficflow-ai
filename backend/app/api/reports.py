from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..services import analytics as an
from ..services.reports import build_report, report_csv
from .deps import filters

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
def report(format: Literal["json", "csv"] = Query("json"), f: an.Filters = Depends(filters),
           db: Session = Depends(get_db)):
    rep = build_report(db, f)
    if format == "csv":
        return Response(report_csv(rep), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="trafficflow_report.csv"'})
    return rep
