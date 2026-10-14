"""Runs the full pipeline on one video source in a background thread:

    read frame -> detect -> track -> count lines / monitor zones -> annotate -> publish

The processor never touches the database or the web layer.  It reports through callbacks, so it can
run inside the FastAPI process today and on an edge device (publishing to the API over HTTP/MQTT)
tomorrow.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

import cv2
import numpy as np

from .config import AIConfig
from .counter import CountEvent, LineCounter, LineDef
from .detector import Detections, ModelNotFoundError, VehicleDetector
from .tracker import Track, build_tracker
from .zones import ZoneDef, ZoneEvent, ZoneMonitor

log = logging.getLogger("trafficflow.processor")

# BGR colours per vehicle type
TYPE_COLORS = {
    "car": (235, 160, 40),
    "motorcycle": (60, 200, 255),
    "bus": (90, 90, 240),
    "truck": (80, 210, 120),
}
DEFAULT_COLOR = (200, 200, 200)


class SourceError(RuntimeError):
    pass


@dataclass
class ProcessorState:
    status: str = "starting"     # starting | running | finished | stopped | error
    message: str = ""
    frame_number: int = 0
    total_frames: int = 0
    fps: float = 0.0
    source_fps: float = 0.0
    total_count: int = 0
    by_type: dict = field(default_factory=dict)
    by_direction: dict = field(default_factory=dict)
    zone_occupancy: dict = field(default_factory=dict)
    active_tracks: int = 0

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class VideoProcessor:
    def __init__(
        self,
        camera_id: int,
        source: str | int,
        source_type: str,
        lines: list[LineDef],
        zones: list[ZoneDef],
        config: AIConfig | None = None,
        on_count: Callable[[CountEvent], None] | None = None,
        on_zone: Callable[[ZoneEvent], None] | None = None,
        on_state: Callable[[ProcessorState], None] | None = None,
        detector: VehicleDetector | None = None,
        tracker_factory: Callable | None = None,
    ):
        self.camera_id = camera_id
        self.source = source
        self.source_type = source_type
        self.lines = lines
        self.zones = zones
        self.config = config or AIConfig()
        self.on_count = on_count or (lambda e: None)
        self.on_zone = on_zone or (lambda e: None)
        self.on_state = on_state or (lambda s: None)
        self.detector = detector or VehicleDetector(self.config)
        self.tracker_factory = tracker_factory or build_tracker

        self.state = ProcessorState()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._jpeg: bytes | None = None
        self._jpeg_lock = threading.Lock()
        self._jpeg_seq = 0

    # ------------------------------------------------------------------ public API
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"processor-cam{self.camera_id}", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def latest_jpeg(self) -> tuple[int, bytes | None]:
        with self._jpeg_lock:
            return self._jpeg_seq, self._jpeg

    # ------------------------------------------------------------------ internals
    def _open(self) -> cv2.VideoCapture:
        src = self.source
        if self.source_type == "webcam":
            src = int(src)
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            cap.release()
            raise SourceError(f"Could not open {self.source_type} source '{self.source}'. "
                              f"Check that the file/device/URL exists and is a supported format.")
        return cap

    def _set_state(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self.state, k, v)

    def _emit_state(self) -> None:
        try:
            self.on_state(self.state)
        except Exception:  # never let a listener kill the pipeline
            log.exception("on_state callback failed")

    def _run(self) -> None:
        cap = None
        try:
            self.detector.load()  # raises ModelNotFoundError with a helpful message
            cap = self._open()
            src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            if not (1 <= src_fps <= 240):
                src_fps = 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) if self.source_type == "video_file" else 0
            ok, first = cap.read()
            if not ok:
                raise SourceError("The source opened but no frames could be read (corrupt or unsupported video?).")
            first = self._resize(first)
            h, w = first.shape[:2]

            skip = max(1, self.config.frame_skip)
            tracker = self.tracker_factory(self.config, max(1, round(src_fps / skip)))
            counter = LineCounter(self.lines, (w, h), max_idle_frames=max(60, int(src_fps * 10)))
            zone_mon = ZoneMonitor(self.zones, (w, h), self.config.zone_exit_grace_frames)

            self._set_state(status="running", message="", source_fps=src_fps, total_frames=total_frames)
            self._emit_state()

            pending = first
            frame_no = 0
            t_start = time.monotonic()
            last_state_emit = 0.0
            fps_window: list[float] = []
            live = self.source_type != "video_file"
            reconnects = 0

            while not self._stop.is_set():
                if pending is not None:
                    frame, pending = pending, None
                else:
                    ok = cap.grab()
                    if not ok:
                        if live and reconnects < 5:  # RTSP/webcam hiccup: try to reconnect
                            reconnects += 1
                            cap.release()
                            time.sleep(min(2 * reconnects, 10))
                            try:
                                cap = self._open()
                                continue
                            except SourceError:
                                continue
                        if self.config.loop_video and not live:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            tracker.reset()
                            counter = LineCounter(self.lines, (w, h), max_idle_frames=max(60, int(src_fps * 10)))
                            zone_mon = ZoneMonitor(self.zones, (w, h), self.config.zone_exit_grace_frames)
                            frame_no = 0
                            t_start = time.monotonic()
                            continue
                        break
                    reconnects = 0
                    frame_no += 1
                    if (frame_no % skip) != 0:
                        self._pace(frame_no, t_start, src_fps, live)
                        continue
                    ok, frame = cap.retrieve()
                    if not ok:
                        continue
                    frame = self._resize(frame)

                # real-time catch-up: if we are >0.75 s behind the video clock, drop frames
                if self.config.realtime_playback and not live:
                    lag = (time.monotonic() - t_start) - frame_no / src_fps
                    if lag > 0.75:
                        drop = int(lag * src_fps * 0.5)
                        for _ in range(drop):
                            if not cap.grab():
                                break
                            frame_no += 1

                t0 = time.monotonic()
                dets: Detections = self.detector.detect(frame)
                tracks: list[Track] = self._safe_track(tracker, dets, frame)
                payload = [
                    {"track_id": t.track_id, "vehicle_type": t.vehicle_type, "confidence": t.confidence,
                     "point": t.reference_point(self.config.reference_point)}
                    for t in tracks
                ]
                for ev in counter.update(payload, frame_no):
                    self._safe_cb(self.on_count, ev)
                for zev in zone_mon.update(payload, frame_no):
                    self._safe_cb(self.on_zone, zev)

                self._publish(self._annotate(frame, tracks, counter, zone_mon))

                dt = time.monotonic() - t0
                fps_window = (fps_window + [dt])[-20:]
                self._set_state(
                    frame_number=frame_no, fps=round(1.0 / (sum(fps_window) / len(fps_window)), 1),
                    total_count=counter.total(), by_type=counter.totals_by_type(),
                    by_direction=counter.totals_by_direction(), zone_occupancy=zone_mon.occupancy(),
                    active_tracks=len(tracks),
                )
                now = time.monotonic()
                if now - last_state_emit > 1.0:
                    last_state_emit = now
                    self._emit_state()
                self._pace(frame_no, t_start, src_fps, live)

            if self._stop.is_set():
                self._set_state(status="stopped", message="Stopped by user")
            else:
                self._set_state(status="finished", message="End of video reached")
        except ModelNotFoundError as e:
            self._set_state(status="error", message=str(e))
        except SourceError as e:
            self._set_state(status="error", message=str(e))
        except Exception as e:  # noqa: BLE001 - never crash silently, surface to UI
            log.exception("Processing failed for camera %s", self.camera_id)
            self._set_state(status="error", message=f"AI processing error: {type(e).__name__}: {e}")
        finally:
            if cap is not None:
                cap.release()
            self._emit_state()

    def _pace(self, frame_no: int, t_start: float, src_fps: float, live: bool) -> None:
        if live or not self.config.realtime_playback:
            return
        ahead = frame_no / src_fps - (time.monotonic() - t_start)
        if ahead > 0:
            self._stop.wait(min(ahead, 0.5))

    def _resize(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if w <= self.config.process_width:
            return frame
        scale = self.config.process_width / w
        return cv2.resize(frame, (self.config.process_width, int(h * scale)), interpolation=cv2.INTER_AREA)

    def _safe_track(self, tracker, dets: Detections, frame) -> list[Track]:
        try:
            return tracker.update(dets, frame)
        except Exception:
            log.exception("tracker.update failed; skipping frame")
            return []

    @staticmethod
    def _safe_cb(cb, ev) -> None:
        try:
            cb(ev)
        except Exception:
            log.exception("event callback failed")

    def _publish(self, img: np.ndarray) -> None:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, self.config.jpeg_quality])
        if ok:
            with self._jpeg_lock:
                self._jpeg = buf.tobytes()
                self._jpeg_seq += 1

    # ------------------------------------------------------------------ drawing
    def _annotate(self, frame: np.ndarray, tracks: list[Track], counter: LineCounter, zm: ZoneMonitor) -> np.ndarray:
        img = frame.copy()
        h, w = img.shape[:2]

        overlay = img.copy()
        for z in self.zones:
            pts = np.array(z.scaled(w, h), dtype=np.int32)
            cv2.fillPoly(overlay, [pts], (255, 160, 40))
            cv2.polylines(img, [pts], True, (255, 190, 90), 2)
        img = cv2.addWeighted(overlay, 0.12, img, 0.88, 0)

        for ln in self.lines:
            a = (int(ln.p1[0] * w), int(ln.p1[1] * h))
            b = (int(ln.p2[0] * w), int(ln.p2[1] * h))
            cv2.line(img, a, b, (40, 40, 255), 3)
            cv2.putText(img, f"{ln.name}: {counter.total(ln.id)}", (a[0] + 6, a[1] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

        for t in tracks:
            x1, y1, x2, y2 = map(int, t.bbox)
            col = TYPE_COLORS.get(t.vehicle_type, DEFAULT_COLOR)
            cv2.rectangle(img, (x1, y1), (x2, y2), col, 2)
            label = f"#{t.track_id} {t.vehicle_type} {t.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(img, (x1, y1 - th - 6), (x1 + tw + 4, y1), col, -1)
            cv2.putText(img, label, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
            cx, cy = map(int, t.reference_point(self.config.reference_point))
            cv2.circle(img, (cx, cy), 3, (255, 255, 255), -1)

        dirs = counter.totals_by_direction()
        lines_txt = [f"Total: {counter.total()}"] + [f"{k}: {v}" for k, v in sorted(counter.totals_by_type().items())]
        lines_txt += [f"{k}: {v}" for k, v in sorted(dirs.items())]
        occ = zm.occupancy()
        if occ:
            lines_txt.append(f"In zone: {sum(occ.values())}")
        pad = 8
        box_h = 20 * len(lines_txt) + pad * 2
        cv2.rectangle(img, (8, 8), (190, 8 + box_h), (20, 20, 20), -1)
        for i, txt in enumerate(lines_txt):
            cv2.putText(img, txt, (14, 8 + pad + 14 + 20 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 1, cv2.LINE_AA)
        return img
