from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..services.prediction import predict

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("")
def predictions(area_id: int | None = Query(None, gt=0), hours: int = Query(6, ge=1, le=24),
                db: Session = Depends(get_db)):
    return predict(db, area_id, hours)
