from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..models import Area, Camera, CountingLine, TrafficSummary, VehicleEvent, ZoneEvent
from ..schemas.schemas import VideoStartRequest, VideoStopRequest
from ..services.processing_manager import ProcessingError, processing
from ..services.video_files import list_videos

router = APIRouter(tags=["video"])


@router.get("/video/files")
def video_files():
    """Videos available in the server's configured /videos folder (names only - no paths)."""
    return list_videos()


@router.post("/video/start")
def start(body: VideoStartRequest):
    try:
        return processing.start(body.camera_id)
    except ProcessingError as e:
        raise HTTPException(e.status_code, str(e))


@router.post("/video/stop")
def stop(body: VideoStopRequest):
    if not processing.stop(body.camera_id):
        raise HTTPException(404, "This camera is not being processed.")
    return {"camera_id": body.camera_id, "status": "stopping"}


@router.get("/video/status")
def status():
    out = {}
    for cid in list(processing._processors):
        p = processing.get(cid)
        out[cid] = {"running": p.running, **p.state.to_dict()}
    return out


@router.get("/video/stream/{camera_id}")
async def stream(camera_id: int):
    """MJPEG stream of the annotated frames (boxes, IDs, counting line). Use as <img src=...>."""
    proc = processing.get(camera_id)
    if proc is None:
        raise HTTPException(404, "This camera is not being processed. Start processing first.")

    async def gen():
        last = -1
        while True:
            p = processing.get(camera_id)
            if p is None:
                break
            seq, jpg = p.latest_jpeg()
            if jpg is not None and seq != last:
                last = seq
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n"
            elif not p.running and jpg is not None:
                # finished: keep the final frame displayed until the client disconnects
                await asyncio.sleep(0.5)
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n"
            await asyncio.sleep(0.04)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame",
                             headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- demo mode
DEMO_CAMERA = "Demo Camera 1"


def _demo_camera(db: Session) -> Camera:
    cam = db.scalar(select(Camera).where(Camera.name == DEMO_CAMERA))
    if cam is None:
        area = db.scalar(select(Area).order_by(Area.id))
        cam = Camera(name=DEMO_CAMERA, location="Demo junction (video file)", area_id=area.id if area else None,
                     source_type="video_file", source_url="demo.mp4", status="offline")
        db.add(cam)
        db.flush()
        db.add(CountingLine(camera_id=cam.id, name="Main line", x1=0.05, y1=0.6, x2=0.95, y2=0.6))
        db.commit()
    return cam


@router.post("/demo/start")
def demo_start(video: str | None = None, db: Session = Depends(get_db)):
    """One-click demo: use `videos/demo.mp4` (or the first video in the folder) on the demo camera."""
    files = [f["name"] for f in list_videos()]
    if not files:
        raise HTTPException(422, "No video found. Copy a traffic video (e.g. demo.mp4) into the /videos folder, "
                                 "then press Start demo again.")
    chosen = video if video in files else ("demo.mp4" if "demo.mp4" in files else files[0])
    cam = _demo_camera(db)
    if processing.is_running(cam.id):
        return {"camera_id": cam.id, "status": "already_running", "video": cam.source_url}
    cam.source_url, cam.source_type, cam.is_active = chosen, "video_file", True
    db.commit()
    try:
        processing.start(cam.id)
    except ProcessingError as e:
        raise HTTPException(e.status_code, str(e))
    return {"camera_id": cam.id, "status": "starting", "video": chosen}


@router.post("/demo/reset")
def demo_reset(db: Session = Depends(get_db)):
    """Clear all stored traffic data of the demo camera so the demo starts from zero."""
    cam = db.scalar(select(Camera).where(Camera.name == DEMO_CAMERA))
    if cam is None:
        return {"deleted_events": 0}
    if processing.is_running(cam.id):
        raise HTTPException(409, "Stop the demo before resetting its data.")
    n = db.execute(delete(VehicleEvent).where(VehicleEvent.camera_id == cam.id)).rowcount
    db.execute(delete(ZoneEvent).where(ZoneEvent.camera_id == cam.id))
    db.execute(delete(TrafficSummary).where(TrafficSummary.camera_id == cam.id))
    db.commit()
    return {"deleted_events": n}
