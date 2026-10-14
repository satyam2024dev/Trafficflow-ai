from datetime import timedelta
from pathlib import Path

import pytest

from app.config import get_settings
from app.services.events import record_vehicle_event
from app.utils.timeutil import now_utc, start_of_today


def add(db, cam, n=1, vt="car", direction="northbound", ts=None):
    for i in range(n):
        record_vehicle_event(db, camera=cam, line_id=None, track_id=i, vehicle_type=vt, direction=direction,
                             confidence=0.8, frame_number=i, timestamp=ts or start_of_today() + timedelta(minutes=5))


@pytest.fixture
def video_file():
    p = get_settings().video_path / "unit.mp4"
    p.write_bytes(b"not a real video")
    yield "unit.mp4"
    p.unlink(missing_ok=True)


# ---------------------------------------------------------------- health
def test_health(client):
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["database"]["ok"] is True
    assert "model" in r and "classes" in r["model"]


# ---------------------------------------------------------------- cameras & validation
def test_camera_crud_and_default_line(client, world, video_file):
    r = client.post("/api/cameras", json={"name": "New", "area_id": world["a1"].id, "source_type": "video_file", "source_url": video_file})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["area_name"] == "Area A" and r.json()["status"] == "offline"
    lines = client.get(f"/api/cameras/{cid}/lines").json()
    assert len(lines) == 1  # auto-created default line
    r = client.put(f"/api/cameras/{cid}", json={"name": "Renamed"})
    assert r.status_code == 200 and r.json()["name"] == "Renamed"
    assert client.delete(f"/api/cameras/{cid}").status_code == 204  # deactivate
    cam = client.get(f"/api/cameras/{cid}").json()
    assert cam["is_active"] is False and cam["status"] == "inactive"
    assert client.delete(f"/api/cameras/{cid}?permanent=true").status_code == 204
    assert client.get(f"/api/cameras/{cid}").status_code == 404


@pytest.mark.parametrize("payload", [
    {"name": "x", "source_type": "video_file", "source_url": "../../etc/passwd"},
    {"name": "x", "source_type": "video_file", "source_url": "C:\\Windows\\video.mp4"},
    {"name": "x", "source_type": "video_file", "source_url": "/etc/passwd"},
    {"name": "x", "source_type": "rtsp", "source_url": "http://not-rtsp"},
    {"name": "x", "source_type": "webcam", "source_url": "abc"},
    {"name": "x", "source_type": "ftp", "source_url": "a.mp4"},
    {"name": "", "source_type": "video_file", "source_url": "a.mp4"},
])
def test_camera_validation_rejects_bad_input(client, payload):
    assert client.post("/api/cameras", json=payload).status_code == 422


def test_camera_missing_video_and_bad_area(client, world):
    r = client.post("/api/cameras", json={"name": "x", "source_type": "video_file", "source_url": "nope.mp4"})
    assert r.status_code == 422 and "not found" in r.json()["detail"]
    r = client.post("/api/cameras", json={"name": "x", "area_id": 9999, "source_type": "rtsp", "source_url": "rtsp://h/s"})
    assert r.status_code == 422


def test_rtsp_camera_can_be_registered(client):
    r = client.post("/api/cameras", json={"name": "Street", "source_type": "rtsp", "source_url": "rtsp://10.0.0.5/stream1"})
    assert r.status_code == 201 and r.json()["source_type"] == "rtsp"


def test_line_and_zone_validation(client, world):
    cid = world["c1"].id
    ok = client.post(f"/api/cameras/{cid}/lines", json={"name": "L2", "x1": 0, "y1": .3, "x2": 1, "y2": .3})
    assert ok.status_code == 201
    assert client.post(f"/api/cameras/{cid}/lines", json={"name": "bad", "x1": 2, "y1": 0, "x2": 1, "y2": 1}).status_code == 422
    assert client.post(f"/api/cameras/{cid}/lines", json={"name": "pt", "x1": .5, "y1": .5, "x2": .5, "y2": .5}).status_code == 422
    z = client.post(f"/api/cameras/{cid}/zones", json={"name": "Z", "polygon": [[0, 0], [1, 0], [1, 1]]})
    assert z.status_code == 201
    assert client.post(f"/api/cameras/{cid}/zones", json={"name": "Z", "polygon": [[0, 0], [1, 0]]}).status_code == 422
    assert client.post(f"/api/cameras/{cid}/zones", json={"name": "Z", "polygon": [[0, 0], [5, 0], [1, 1]]}).status_code == 422


# ---------------------------------------------------------------- areas
def test_areas(client):
    r = client.post("/api/areas", json={"name": "Zone X", "latitude": 10, "longitude": 20, "hourly_capacity": 800})
    assert r.status_code == 201
    assert client.post("/api/areas", json={"name": "Zone X"}).status_code == 409
    assert client.post("/api/areas", json={"name": "Bad", "latitude": 123}).status_code == 422
    assert any(a["name"] == "Zone X" for a in client.get("/api/areas").json())


# ---------------------------------------------------------------- analytics endpoints
def test_traffic_endpoints_use_database_data(client, world, db):
    add(db, world["c1"], 4, "car"); add(db, world["c1"], 2, "bus", "southbound"); add(db, world["c3"], 1, "truck")
    assert client.get("/api/traffic/today").json()["total"] == 7
    assert client.get("/api/traffic/today", params={"area_id": world["a1"].id}).json()["total"] == 6
    assert {x["vehicle_type"]: x["count"] for x in client.get("/api/traffic/by-type").json()} == {"car": 4, "bus": 2, "truck": 1}
    assert len(client.get("/api/traffic/by-area").json()) == 2
    assert client.get("/api/traffic/by-camera").json()[0]["camera_name"] == "Cam 1"
    assert sum(h["count"] for h in client.get("/api/traffic/hourly").json()) == 7
    assert len(client.get("/api/traffic/daily?days=7").json()) == 7
    assert len(client.get("/api/traffic/weekly").json()) == 8
    assert len(client.get("/api/traffic/monthly").json()) == 12
    assert {d["direction"] for d in client.get("/api/traffic/by-direction").json()} == {"northbound", "southbound"}
    assert len(client.get("/api/traffic/peak-hours").json()["hours"]) == 24
    assert client.get("/api/traffic/trends").status_code == 200
    assert len(client.get("/api/traffic/map").json()) == 3


def test_empty_database_returns_zeros_not_errors(client):
    assert client.get("/api/traffic/today").json()["total"] == 0
    assert client.get("/api/traffic/by-type").json() == []
    assert all(h["count"] == 0 for h in client.get("/api/traffic/hourly").json())


def test_invalid_filters_rejected(client):
    assert client.get("/api/traffic/today?start_date=2025-02-01&end_date=2025-01-01").status_code == 422
    assert client.get("/api/traffic/hourly?hours=0").status_code == 422
    assert client.get("/api/traffic/by-type?vehicle_type=car;drop table").status_code == 422
    assert client.get("/api/events?page=0").status_code == 422
    assert client.get("/api/events?sort_by=password").status_code == 422
    assert client.get("/api/traffic/today?area_id=abc").status_code == 422


# ---------------------------------------------------------------- events: filter / sort / paginate / export
def test_events_pagination_sorting_search_export(client, world, db):
    add(db, world["c1"], 5, "car"); add(db, world["c2"], 3, "bus", "southbound"); add(db, world["c3"], 2, "truck")
    r = client.get("/api/events", params={"page": 1, "page_size": 4}).json()
    assert r["total"] == 10 and len(r["items"]) == 4
    assert client.get("/api/events", params={"page": 3, "page_size": 4}).json()["items"].__len__() == 2
    r = client.get("/api/events", params={"vehicle_type": "bus"}).json()
    assert r["total"] == 3 and all(i["vehicle_type"] == "bus" and i["camera_name"] == "Cam 2" for i in r["items"])
    assert client.get("/api/events", params={"direction": "southbound"}).json()["total"] == 3
    assert client.get("/api/events", params={"area_id": world["a2"].id}).json()["total"] == 2
    assert client.get("/api/events", params={"search": "truck"}).json()["total"] == 2
    assert client.get("/api/events", params={"search": "Cam 2"}).json()["total"] == 3
    asc = client.get("/api/events", params={"sort_by": "vehicle_type", "order": "asc", "page_size": 50}).json()["items"]
    assert [i["vehicle_type"] for i in asc] == sorted(i["vehicle_type"] for i in asc)
    today = start_of_today().date().isoformat()
    assert client.get("/api/events", params={"start_date": today, "end_date": today}).json()["total"] == 10
    assert client.get("/api/events", params={"start_date": "2001-01-01", "end_date": "2001-01-02"}).json()["total"] == 0
    csv = client.get("/api/events/export", params={"vehicle_type": "car"})
    assert csv.headers["content-type"].startswith("text/csv")
    lines = csv.text.strip().splitlines()
    assert lines[0].startswith("id,timestamp,camera") and len(lines) == 6


def test_report_csv_and_json(client, world, db):
    add(db, world["c1"], 3, "car"); add(db, world["c1"], 1, "bus")
    j = client.get("/api/reports").json()
    assert j["total_vehicles"] == 4 and j["by_type"][0]["vehicle_type"] == "car"
    c = client.get("/api/reports", params={"format": "csv"})
    assert "Vehicle type distribution" in c.text and "TOTAL,4" in c.text and "Peak hours" in c.text
    assert client.get("/api/reports?format=pdf").status_code == 422


# ---------------------------------------------------------------- predictions
def test_prediction_insufficient_then_ok(client, world, db):
    r = client.get("/api/predictions").json()
    assert r["status"] == "insufficient_data" and r["predictions"] == [] and r["is_prediction"] is True
    past = now_utc() - timedelta(hours=26)
    for k in range(5):
        add(db, world["c1"], 40 + k * 10, ts=past - timedelta(hours=k * 24))  # same hour on several days
    r = client.get("/api/predictions", params={"hours": 24, "area_id": world["a1"].id}).json()
    assert r["status"] == "ok" and len(r["predictions"]) == 24
    assert "not guaranteed" in r["disclaimer"]
    assert all(p["traffic_status"] in ("LOW", "MODERATE", "HIGH", "CRITICAL") for p in r["predictions"])
    assert max(p["predicted_vehicles"] for p in r["predictions"]) > 0
    assert client.get("/api/predictions?hours=99").status_code == 422


# ---------------------------------------------------------------- video control & security
def test_video_start_errors_are_clear(client, world, db):
    assert client.post("/api/video/start", json={"camera_id": 9999}).status_code == 404
    assert client.post("/api/video/start", json={"camera_id": 0}).status_code == 422
    r = client.post("/api/video/start", json={"camera_id": world["c1"].id})  # x.mp4 does not exist
    assert r.status_code == 422 and "not found" in r.json()["detail"]
    assert client.get(f"/api/cameras/{world['c1'].id}").json()["status"] == "error"
    assert client.post("/api/video/stop", json={"camera_id": world["c1"].id}).status_code == 404
    assert client.get(f"/api/video/stream/{world['c1'].id}").status_code == 404


def test_video_start_requires_line_or_zone(client, world):
    r = client.post("/api/video/start", json={"camera_id": world["c2"].id})  # c2 has no line
    assert r.status_code == 422 and "counting line" in r.json()["detail"]


def test_video_file_listing_and_traversal(client, video_file):
    names = [f["name"] for f in client.get("/api/video/files").json()]
    assert video_file in names
    from app.services.video_files import VideoFileError, resolve_video
    for bad in ["../x.mp4", "..\\x.mp4", "/etc/passwd", ".hidden.mp4", "a.exe", "", "sub/a.mp4"]:
        with pytest.raises(VideoFileError):
            resolve_video(bad)
    assert resolve_video(video_file).name == video_file


# ---------------------------------------------------------------- websocket + db outage
def test_websocket_hello_and_ping(client):
    with client.websocket_connect("/ws/traffic") as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_text("ping")
        assert ws.receive_json()["type"] == "pong"


def test_websocket_broadcast_reaches_client(client):
    from app.websocket.manager import manager
    with client.websocket_connect("/ws/traffic") as ws:
        ws.receive_json()
        manager.broadcast_threadsafe({"type": "vehicle_event", "event": {"vehicle_type": "car"}})
        assert ws.receive_json()["event"]["vehicle_type"] == "car"


def test_database_down_returns_503(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.exc import OperationalError
    from app.main import app
    from app.database.session import get_db

    def broken():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))
        yield
    app.dependency_overrides[get_db] = broken
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/api/traffic/today")
            assert r.status_code == 503 and "database is unavailable" in r.json()["detail"]
    finally:
        app.dependency_overrides.clear()
