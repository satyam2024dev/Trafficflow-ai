from __future__ import annotations

import cv2
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..models import Area, Camera, CountingLine, Zone
from ..schemas.schemas import (CameraCreate, CameraOut, CameraUpdate, LineCreate, LineOut, ZoneCreate, ZoneOut)
from ..services.processing_manager import processing
from ..services.video_files import VideoFileError, resolve_video

router = APIRouter(tags=["cameras"])


def _out(cam: Camera) -> CameraOut:
    o = CameraOut.model_validate(cam)
    o.area_name = cam.area.name if cam.area else None
    o.processing = processing.is_running(cam.id)
    if o.processing:
        o.status = "processing"
    return o


def _check_source(source_type: str, source_url: str) -> None:
    if source_type == "video_file":
        try:
            resolve_video(source_url)
        except VideoFileError as e:
            raise HTTPException(422, str(e))


def _get_cam(db: Session, camera_id: int) -> Camera:
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    return cam


@router.get("/cameras", response_model=list[CameraOut])
def list_cameras(include_inactive: bool = True, db: Session = Depends(get_db)):
    q = select(Camera).order_by(Camera.id)
    if not include_inactive:
        q = q.where(Camera.is_active.is_(True))
    return [_out(c) for c in db.scalars(q).all()]


@router.get("/cameras/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: int, db: Session = Depends(get_db)):
    return _out(_get_cam(db, camera_id))


@router.post("/cameras", response_model=CameraOut, status_code=201)
def create_camera(body: CameraCreate, db: Session = Depends(get_db)):
    if body.area_id and not db.get(Area, body.area_id):
        raise HTTPException(422, "Selected area does not exist")
    _check_source(body.source_type, body.source_url)
    cam = Camera(**body.model_dump(), status="offline")
    db.add(cam)
    db.flush()
    # A starting counting line so the camera can be processed immediately; edit it on Live Monitoring.
    db.add(CountingLine(camera_id=cam.id, name="Main line", x1=0.05, y1=0.6, x2=0.95, y2=0.6))
    db.commit()
    db.refresh(cam)
    return _out(cam)


@router.put("/cameras/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: int, body: CameraUpdate, db: Session = Depends(get_db)):
    cam = _get_cam(db, camera_id)
    data = body.model_dump(exclude_unset=True)
    if processing.is_running(camera_id) and ({"source_type", "source_url"} & data.keys()):
        raise HTTPException(409, "Stop processing before changing the camera source.")
    if data.get("area_id") and not db.get(Area, data["area_id"]):
        raise HTTPException(422, "Selected area does not exist")
    st = data.get("source_type", cam.source_type)
    su = data.get("source_url", cam.source_url)
    if {"source_type", "source_url"} & data.keys():
        CameraCreate(name=cam.name, source_type=st, source_url=su)  # reuse validation rules
        _check_source(st, su)
    for k, v in data.items():
        setattr(cam, k, v)
    if "is_active" in data:
        cam.status = "offline" if data["is_active"] else "inactive"
    db.commit()
    db.refresh(cam)
    return _out(cam)


@router.delete("/cameras/{camera_id}", status_code=204)
def delete_camera(camera_id: int, permanent: bool = False, db: Session = Depends(get_db)):
    """Default: deactivate (history is kept). ?permanent=true deletes the camera and all its events."""
    cam = _get_cam(db, camera_id)
    processing.stop(camera_id)
    if permanent:
        db.delete(cam)
    else:
        cam.is_active, cam.status = False, "inactive"
    db.commit()


@router.get("/cameras/{camera_id}/snapshot")
def snapshot(camera_id: int, db: Session = Depends(get_db)):
    """A single frame, used by the line editor. Video files only; never accepts a client path."""
    cam = _get_cam(db, camera_id)
    proc = processing.get(camera_id)
    if proc and proc.running:
        _, jpg = proc.latest_jpeg()
        if jpg:
            return Response(jpg, media_type="image/jpeg")
    if cam.source_type != "video_file":
        raise HTTPException(409, "Snapshots for webcam/RTSP cameras are only available while processing.")
    try:
        path = resolve_video(cam.source_url)
    except VideoFileError as e:
        raise HTTPException(422, str(e))
    cap = cv2.VideoCapture(str(path))
    try:
        ok, frame = cap.read()
    finally:
        cap.release()
    if not ok:
        raise HTTPException(422, "Could not read a frame from this video file.")
    h, w = frame.shape[:2]
    if w > 960:
        frame = cv2.resize(frame, (960, int(h * 960 / w)))
    ok, buf = cv2.imencode(".jpg", frame)
    return Response(buf.tobytes(), media_type="image/jpeg")


# ---------------------------------------------------------------- counting lines
@router.get("/cameras/{camera_id}/lines", response_model=list[LineOut])
def list_lines(camera_id: int, db: Session = Depends(get_db)):
    _get_cam(db, camera_id)
    return db.scalars(select(CountingLine).where(CountingLine.camera_id == camera_id).order_by(CountingLine.id)).all()


@router.post("/cameras/{camera_id}/lines", response_model=LineOut, status_code=201)
def add_line(camera_id: int, body: LineCreate, db: Session = Depends(get_db)):
    _get_cam(db, camera_id)
    line = CountingLine(camera_id=camera_id, **body.model_dump())
    db.add(line)
    db.commit()
    return line


@router.put("/lines/{line_id}", response_model=LineOut)
def update_line(line_id: int, body: LineCreate, db: Session = Depends(get_db)):
    line = db.get(CountingLine, line_id)
    if not line:
        raise HTTPException(404, "Counting line not found")
    for k, v in body.model_dump().items():
        setattr(line, k, v)
    db.commit()
    return line


@router.delete("/lines/{line_id}", status_code=204)
def delete_line(line_id: int, db: Session = Depends(get_db)):
    line = db.get(CountingLine, line_id)
    if not line:
        raise HTTPException(404, "Counting line not found")
    db.delete(line)
    db.commit()


# ---------------------------------------------------------------- zones
@router.get("/cameras/{camera_id}/zones", response_model=list[ZoneOut])
def list_zones(camera_id: int, db: Session = Depends(get_db)):
    _get_cam(db, camera_id)
    return db.scalars(select(Zone).where(Zone.camera_id == camera_id).order_by(Zone.id)).all()


@router.post("/cameras/{camera_id}/zones", response_model=ZoneOut, status_code=201)
def add_zone(camera_id: int, body: ZoneCreate, db: Session = Depends(get_db)):
    _get_cam(db, camera_id)
    z = Zone(camera_id=camera_id, name=body.name, polygon=[list(p) for p in body.polygon])
    db.add(z)
    db.commit()
    return z


@router.delete("/zones/{zone_id}", status_code=204)
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    z = db.get(Zone, zone_id)
    if not z:
        raise HTTPException(404, "Zone not found")
    db.delete(z)
    db.commit()
