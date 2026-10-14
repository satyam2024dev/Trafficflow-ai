"""Video file -> processor -> queue -> PostgreSQL -> analytics API -> WebSocket (detector is a test double)."""
import time

import pytest

from app.config import get_settings
from app.models import Camera, CountingLine, TrafficSummary, VehicleEvent, ZoneEvent
from app.services.processing_manager import processing
from sqlalchemy import func, select
from ai.tracker import CentroidTracker
from tests.ai.synthetic import ColorBlobDetector, make_video
from tests.ai.test_pipeline import PLAN


@pytest.fixture
def e2e(monkeypatch, db, world):
    monkeypatch.setenv("REALTIME_PLAYBACK", "false"); monkeypatch.setenv("FRAME_SKIP", "1")
    monkeypatch.setenv("TRACKER", "centroid"); monkeypatch.setenv("PROCESS_WIDTH", "640")
    processing.detector_factory = ColorBlobDetector
    processing.tracker_factory = lambda cfg, fps: CentroidTracker(cfg)
    path = get_settings().video_path / "e2e.mp4"
    make_video(str(path), PLAN)
    cam = db.get(Camera, world["c1"].id); cam.source_url = "e2e.mp4"
    db.query(CountingLine).filter_by(camera_id=cam.id).update({"x1": 0, "y1": .5, "x2": 1, "y2": .5})
    db.commit()
    processing.startup()
    yield cam
    processing.detector_factory = processing.tracker_factory = None
    path.unlink(missing_ok=True)


def wait_done(cid, timeout=40):
    p = processing.get(cid)
    for _ in range(int(timeout / 0.1)):
        if not p.running:
            break
        time.sleep(0.1)
    time.sleep(1.0)  # let the writer thread drain the queue
    return p


def test_full_flow_events_in_postgres_and_dashboard_api(client, e2e, db):
    with client.websocket_connect("/ws/traffic") as ws:
        ws.receive_json()
        assert client.post("/api/video/start", json={"camera_id": e2e.id}).status_code == 200
        assert client.post("/api/video/start", json={"camera_id": e2e.id}).status_code in (200, 409)
        p = wait_done(e2e.id)
        assert p.state.status == "finished", p.state.message

        types = []
        while True:   # drain WebSocket messages produced during processing
            try:
                m = ws.receive_json(mode="text") if False else ws.receive_json()
            except Exception:
                break
            if m["type"] == "vehicle_event":
                types.append(m["event"]["vehicle_type"])
            if len(types) == 3:
                break
        assert sorted(types) == ["bus", "car", "truck"]          # live updates reached the dashboard

    db.expire_all()
    rows = db.scalars(select(VehicleEvent).order_by(VehicleEvent.id)).all()
    assert sorted((r.vehicle_type, r.direction) for r in rows) == [("bus", "northbound"), ("car", "southbound"), ("truck", "southbound")]
    assert all(r.area_id == e2e.area_id and 0 < r.confidence <= 1 for r in rows)
    assert db.scalar(select(func.sum(TrafficSummary.vehicle_count))) == 3
    assert db.scalar(select(func.count()).select_from(ZoneEvent)) == 0  # camera 1 had no zone configured

    today = client.get("/api/traffic/today").json()
    assert today["total"] == 3 and today["by_type"]["bus"] == 1
    assert {d["direction"]: d["count"] for d in client.get("/api/traffic/by-direction").json()} == {"southbound": 2, "northbound": 1}
    assert client.get("/api/events").json()["total"] == 3
    assert client.get(f"/api/cameras/{e2e.id}").json()["status"] == "online"
    stream_seq, jpg = processing.get(e2e.id).latest_jpeg()
    assert jpg[:2] == b"\xff\xd8"


def test_corrupt_video_reports_error_state(client, world, db, monkeypatch):
    """With the model check bypassed, a non-video file must surface a clear error and set camera status."""
    processing.detector_factory = ColorBlobDetector
    processing.tracker_factory = lambda cfg, fps: CentroidTracker(cfg)
    bad = get_settings().video_path / "corrupt.mp4"; bad.write_bytes(b"not a video")
    try:
        cam = db.get(Camera, world["c1"].id); cam.source_url = "corrupt.mp4"; db.commit()
        processing.startup()
        client.post("/api/video/start", json={"camera_id": cam.id})
        p = wait_done(cam.id, 10)
        assert p.state.status == "error" and "open" in p.state.message.lower()
        db.expire_all()
        c = db.get(Camera, cam.id)
        assert c.status == "error" and "open" in c.last_error.lower()
    finally:
        processing.detector_factory = processing.tracker_factory = None
        bad.unlink(missing_ok=True)
