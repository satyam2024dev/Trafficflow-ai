from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..models import Area
from ..schemas.schemas import AreaCreate, AreaOut, AreaUpdate

router = APIRouter(prefix="/areas", tags=["areas"])


@router.get("", response_model=list[AreaOut])
def list_areas(db: Session = Depends(get_db)):
    return db.scalars(select(Area).order_by(Area.name)).all()


@router.post("", response_model=AreaOut, status_code=201)
def create_area(body: AreaCreate, db: Session = Depends(get_db)):
    area = Area(**body.model_dump())
    db.add(area)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"An area named '{body.name}' already exists.")
    return area


@router.put("/{area_id}", response_model=AreaOut)
def update_area(area_id: int, body: AreaUpdate, db: Session = Depends(get_db)):
    area = db.get(Area, area_id)
    if not area:
        raise HTTPException(404, "Area not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(area, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An area with that name already exists.")
    return area


@router.delete("/{area_id}", status_code=204)
def delete_area(area_id: int, db: Session = Depends(get_db)):
    area = db.get(Area, area_id)
    if not area:
        raise HTTPException(404, "Area not found")
    db.delete(area)  # cameras/events keep their rows; area_id becomes NULL
    db.commit()
