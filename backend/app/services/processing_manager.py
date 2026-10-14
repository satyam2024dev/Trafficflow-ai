"""Owns the running video processors.

AI inference runs in one thread per camera (CPU/GPU heavy, never on the asyncio loop).  Events are
handed through a queue to a single writer thread which persists them to PostgreSQL and then pushes
them to the dashboard over WebSocket:

    VideoProcessor thread -> queue -> writer thread -> PostgreSQL -> WebSocket -> React
"""
from __future__ import annotations

import logging
import queue
import sys
import threading

from sqlalchemy import select

from ..config import REPO_ROOT, get_settings
from ..database.session import SessionLocal
from ..models import Camera, CountingLine, Zone
from ..utils.timeutil import now_utc
from ..websocket.manager import manager
from .events import record_vehicle_event, record_zone_event
from .video_files import resolve_video

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

log = logging.getLogger("trafficflow.manager")

MAX_CONCURRENT = 2


class ProcessingError(RuntimeError):
    """User-facing problem starting a processor (maps to HTTP 4xx)."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class ProcessingManager:
    def __init__(self) -> None:
        self._processors: dict[int, object] = {}
        self._queue: queue.Queue = queue.Queue(maxsize=5000)
        self._writer: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_status: dict[int, str] = {}
        self._lock = threading.Lock()
        # Test seams: replace the detector/tracker (e.g. synthetic detector in integration tests).
        self.detector_factory = None
        self.tracker_factory = None

    # ------------------------------------------------------------------ lifecycle
    def startup(self) -> None:
        if self._writer and self._writer.is_alive():
            return
        self._stop.clear()
        self._writer = threading.Thread(target=self._write_loop, name="event-writer", daemon=True)
        self._writer.start()
        try:  # a crash/kill may have left cameras flagged as 'processing'
            with SessionLocal() as db:
                for cam in db.scalars(select(Camera).where(Camera.status == "processing")):
                    cam.status = "offline"
                db.commit()
        except Exception:
            log.warning("Could not reset stale camera states (database unavailable?)")

    def shutdown(self) -> None:
        for cid in list(self._processors):
            self.stop(cid)
        self._stop.set()
        self._queue.put(None)

    # ------------------------------------------------------------------ control
    def is_running(self, camera_id: int) -> bool:
        p = self._processors.get(camera_id)
        return bool(p and p.running)

    def running_ids(self) -> set[int]:
        return {cid for cid, p in self._processors.items() if p.running}

    def get(self, camera_id: int):
        return self._processors.get(camera_id)

    def start(self, camera_id: int) -> dict:
        from ai.config import AIConfig
        from ai.counter import LineDef
        from ai.video_processor import VideoProcessor
        from ai.zones import ZoneDef

        with self._lock:
            if self.is_running(camera_id):
                raise ProcessingError("This camera is already being processed.", 409)
            if len(self.running_ids()) >= MAX_CONCURRENT:
                raise ProcessingError(f"At most {MAX_CONCURRENT} cameras can be processed at once on this machine.", 409)

            with SessionLocal() as db:
                cam = db.get(Camera, camera_id)
                if cam is None:
                    raise ProcessingError("Camera not found.", 404)
                if not cam.is_active:
                    raise ProcessingError("Camera is deactivated. Re-activate it first.", 409)
                lines = [LineDef(l.id, l.name, (l.x1, l.y1), (l.x2, l.y2), l.direction_ab, l.direction_ba)
                         for l in db.scalars(select(CountingLine).where(CountingLine.camera_id == camera_id,
                                                                        CountingLine.is_active.is_(True)))]
                zones = [ZoneDef(z.id, z.name, [tuple(p) for p in z.polygon])
                         for z in db.scalars(select(Zone).where(Zone.camera_id == camera_id, Zone.is_active.is_(True)))]
                if not lines and not zones:
                    raise ProcessingError("Add at least one counting line or zone to this camera before starting.", 422)
                source_type, source_url = cam.source_type, cam.source_url
                if source_type == "video_file":
                    try:
                        source = str(resolve_video(source_url))
                    except ValueError as e:
                        cam.status, cam.last_error = "error", str(e)
                        db.commit()
                        raise ProcessingError(str(e), 422)
                else:
                    source = source_url
                cam.status, cam.last_error = "processing", None
                db.commit()

            proc = VideoProcessor(
                camera_id, source, source_type, lines, zones, AIConfig(),
                on_count=lambda ev, cid=camera_id: self._enqueue("count", cid, ev),
                on_zone=lambda ev, cid=camera_id: self._enqueue("zone", cid, ev),
                on_state=lambda st, cid=camera_id: self._enqueue("state", cid, st.to_dict()),
                detector=self.detector_factory() if self.detector_factory else None,
                tracker_factory=self.tracker_factory,
            )
            self._processors[camera_id] = proc
            self._last_status[camera_id] = "starting"
            proc.start()
        return {"camera_id": camera_id, "status": "starting"}

    def stop(self, camera_id: int) -> bool:
        p = self._processors.get(camera_id)
        if not p:
            return False
        p.stop()
        return True

    # ------------------------------------------------------------------ queue plumbing
    def _enqueue(self, kind: str, camera_id: int, payload) -> None:
        try:
            self._queue.put_nowait((kind, camera_id, payload))
        except queue.Full:
            log.error("Event queue full - dropping %s event for camera %s", kind, camera_id)

    def _write_loop(self) -> None:
        while not self._stop.is_set():
            item = self._queue.get()
            if item is None:
                break
            kind, cid, payload = item
            try:
                if kind == "count":
                    self._handle_count(cid, payload)
                elif kind == "zone":
                    self._handle_zone(cid, payload)
                else:
                    self._handle_state(cid, payload)
            except Exception:
                log.exception("Failed to persist %s event for camera %s", kind, cid)
                manager.broadcast_threadsafe({"type": "error", "camera_id": cid,
                                              "message": "A traffic event could not be saved to the database."})

    def _handle_count(self, cid: int, ev) -> None:
        ts = now_utc()
        with SessionLocal() as db:
            cam = db.get(Camera, cid)
            if cam is None:
                return
            row = record_vehicle_event(db, camera=cam, line_id=ev.line_id, track_id=ev.track_id,
                                       vehicle_type=ev.vehicle_type, direction=ev.direction,
                                       confidence=ev.confidence, frame_number=ev.frame_number, timestamp=ts)
            msg = {"type": "vehicle_event", "event": {
                "id": row.id, "camera_id": cid, "camera_name": cam.name, "area_id": cam.area_id,
                "area_name": cam.area.name if cam.area else None, "track_id": ev.track_id,
                "vehicle_type": ev.vehicle_type, "direction": ev.direction,
                "confidence": round(ev.confidence, 3), "timestamp": ts.isoformat(), "line_name": ev.line_name}}
        manager.broadcast_threadsafe(msg)

    def _handle_zone(self, cid: int, zev) -> None:
        with SessionLocal() as db:
            cam = db.get(Camera, cid)
            if cam is None:
                return
            record_zone_event(db, camera=cam, zone_id=zev.zone_id, track_id=zev.track_id,
                              vehicle_type=zev.vehicle_type, event_type=zev.event_type, frame_number=zev.frame_number)
        manager.broadcast_threadsafe({"type": "zone_event", "camera_id": cid, "zone_id": zev.zone_id,
                                      "event_type": zev.event_type, "vehicle_type": zev.vehicle_type,
                                      "track_id": zev.track_id})

    def _handle_state(self, cid: int, st: dict) -> None:
        status = st["status"]
        if status in ("error", "finished", "stopped") and self._last_status.get(cid) != status:
            with SessionLocal() as db:
                cam = db.get(Camera, cid)
                if cam:
                    cam.status = "error" if status == "error" else "online"
                    cam.last_error = st["message"] if status == "error" else None
                    db.commit()
        self._last_status[cid] = status
        manager.broadcast_threadsafe({"type": "processor_state", "camera_id": cid, "state": st})


processing = ProcessingManager()
