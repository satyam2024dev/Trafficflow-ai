"""Pipeline test on a synthetic video with known ground truth (real video I/O, tracking, counting)."""
import time

import pytest

from ai.config import AIConfig
from ai.counter import LineDef
from ai.video_processor import VideoProcessor
from ai.zones import ZoneDef
from tests.ai.synthetic import ColorBlobDetector, make_video

# Line at y = 0.5*480 = 240.  Ground truth: 3 vehicles cross, 1 never reaches the line.
PLAN = [
    {"type": "car", "x": 150, "y0": 130, "y1": 380, "start": 5, "end": 60},     # down  -> southbound
    {"type": "bus", "x": 320, "y0": 400, "y1": 120, "start": 20, "end": 90},    # up    -> northbound
    {"type": "truck", "x": 500, "y0": 130, "y1": 360, "start": 40, "end": 110}, # down  -> southbound
    {"type": "car", "x": 400, "y0": 130, "y1": 200, "start": 10, "end": 80},    # stops short of the line
]


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    p = tmp_path_factory.mktemp("vid") / "synthetic.mp4"
    make_video(str(p), PLAN)
    return str(p)


def run(video, tracker="centroid", skip=1):
    cfg = AIConfig(); cfg.tracker, cfg.frame_skip, cfg.realtime_playback, cfg.process_width = tracker, skip, False, 640
    events, zone_events = [], []
    proc = VideoProcessor(1, video, "video_file", [LineDef(1, "L", (0.0, 0.5), (1.0, 0.5))],
                          [ZoneDef(1, "Z", [(0, 0.3), (1, 0.3), (1, 0.8), (0, 0.8)])], cfg,
                          on_count=events.append, on_zone=zone_events.append, detector=ColorBlobDetector())
    proc.start()
    for _ in range(300):
        if not proc.running:
            break
        time.sleep(0.05)
    return proc, events, zone_events


def test_each_vehicle_counted_exactly_once_with_type_and_direction(video):
    proc, events, _ = run(video)
    assert proc.state.status == "finished", proc.state.message
    got = sorted((e.vehicle_type, e.direction) for e in events)
    assert got == [("bus", "northbound"), ("car", "southbound"), ("truck", "southbound")]
    assert len({e.track_id for e in events}) == 3          # no duplicate counts
    assert proc.state.total_count == 3 and proc.state.by_type == {"car": 1, "bus": 1, "truck": 1}


def test_frame_skipping_still_counts_correctly(video):
    _, events, _ = run(video, skip=3)
    assert sorted(e.vehicle_type for e in events) == ["bus", "car", "truck"]


def test_zone_events_and_annotated_frames(video):
    proc, _, zev = run(video)
    kinds = [e.event_type for e in zev]
    assert kinds.count("enter") >= 3 and kinds.count("exit") >= 3
    seq, jpg = proc.latest_jpeg()
    assert seq > 10 and jpg[:2] == b"\xff\xd8"          # real annotated JPEG frames were produced


def test_bad_video_reports_error(tmp_path):
    bad = tmp_path / "bad.mp4"; bad.write_bytes(b"garbage")
    cfg = AIConfig(); cfg.tracker = "centroid"
    p = VideoProcessor(1, str(bad), "video_file", [], [], cfg, detector=ColorBlobDetector())
    p.start(); time.sleep(1.0)
    assert p.state.status == "error" and "open" in p.state.message.lower() or "frames" in p.state.message.lower()


def test_missing_model_gives_helpful_error(tmp_path):
    cfg = AIConfig(); cfg.model_path = str(tmp_path / "nope.pt")
    p = VideoProcessor(1, "x.mp4", "video_file", [], [], cfg)
    p.start(); time.sleep(0.5)
    assert p.state.status == "error" and "download_model" in p.state.message
