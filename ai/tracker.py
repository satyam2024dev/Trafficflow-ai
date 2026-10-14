"""Multi-object tracking on top of detector output.

* ``bytetrack`` (default) / ``botsort``: Ultralytics implementations, fed explicitly with the detections
  from detector.py (verified against ultralytics 8.4: BYTETracker(args), update(results, img) ->
  rows of [x1, y1, x2, y2, id, conf, cls, idx]).
* ``centroid``: small dependency-free IoU tracker (no PyTorch). Used for tests / emergency fallback.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from .config import AIConfig
from .detector import Detections


@dataclass
class Track:
    track_id: int
    vehicle_type: str
    confidence: float
    bbox: tuple[float, float, float, float]

    def to_dict(self) -> dict:
        return {"track_id": self.track_id, "vehicle_type": self.vehicle_type,
                "confidence": round(self.confidence, 3), "bbox": [round(v, 1) for v in self.bbox]}

    def reference_point(self, mode: str = "center") -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, y2 if mode == "bottom_center" else (y1 + y2) / 2)


class Tracker(Protocol):
    def update(self, detections: Detections, frame: np.ndarray) -> list[Track]: ...
    def reset(self) -> None: ...


class UltralyticsTracker:
    def __init__(self, config: AIConfig | None = None, frame_rate: int = 30):
        self.config = config or AIConfig()
        self.frame_rate = frame_rate
        self._tracker = None
        self._build()

    def _build(self) -> None:
        import yaml
        from ultralytics.utils import ROOT, IterableSimpleNamespace

        name = self.config.tracker.lower()
        if name not in ("bytetrack", "botsort"):
            raise ValueError(f"Unsupported TRACKER '{self.config.tracker}' (use bytetrack, botsort or centroid)")
        with open(Path(ROOT) / "cfg" / "trackers" / f"{name}.yaml", encoding="utf-8") as fh:
            cfg = IterableSimpleNamespace(**yaml.safe_load(fh))
        cfg.device = "cpu"  # only used by ReID encoders, which we never enable
        if name == "bytetrack":
            from ultralytics.trackers.byte_tracker import BYTETracker as Cls
        else:
            from ultralytics.trackers.bot_sort import BOTSORT as Cls
            cfg.with_reid = False
        kwargs = {"args": cfg}
        if "frame_rate" in inspect.signature(Cls.__init__).parameters:  # older releases
            kwargs["frame_rate"] = self.frame_rate
        self._tracker = Cls(**kwargs)

    def reset(self) -> None:
        self._build()

    def update(self, detections: Detections, frame: np.ndarray) -> list[Track]:
        names = self.config.vehicle_classes
        out: list[Track] = []
        for r in self._tracker.update(detections, frame):
            cid = int(r[6])
            out.append(Track(int(r[4]), names.get(cid, str(cid)), float(r[5]),
                             (float(r[0]), float(r[1]), float(r[2]), float(r[3]))))
        return out


def _iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)
    x1 = np.maximum(a[:, None, 0], b[None, :, 0]); y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2]); y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    aa = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1]); ab = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / (aa[:, None] + ab[None, :] - inter + 1e-9)


class CentroidTracker:
    """Greedy IoU association with constant-velocity prediction; survives short detection gaps."""

    def __init__(self, config: AIConfig | None = None, max_lost: int = 15, min_iou: float = 0.1,
                 min_hits: int = 2, max_center_dist: float = 1.5):
        self.config = config or AIConfig()
        self.max_lost, self.min_iou, self.min_hits, self.max_center_dist = max_lost, min_iou, min_hits, max_center_dist
        self.reset()

    def reset(self) -> None:
        self._tracks: dict[int, dict] = {}
        self._next = 1

    @staticmethod
    def _c(b):
        return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)

    def update(self, detections: Detections, frame=None) -> list[Track]:
        boxes = np.asarray(detections.xyxy, dtype=np.float32).reshape(-1, 4)
        ids = list(self._tracks)
        preds = np.array([self._predict(self._tracks[i]) for i in ids], dtype=np.float32).reshape(-1, 4)
        iou = _iou(preds, boxes)
        mt, md = set(), set()
        pairs = sorted(((float(iou[i, j]), i, j) for i in range(len(ids)) for j in range(len(boxes))), reverse=True)
        # also consider near-miss pairs (IoU 0) by distance
        for score, i, j in pairs:
            if i in mt or j in md:
                continue
            pc, dc = self._c(preds[i]), self._c(boxes[j])
            size = max(boxes[j, 2] - boxes[j, 0], boxes[j, 3] - boxes[j, 1], 1.0)
            dist = ((pc[0] - dc[0]) ** 2 + (pc[1] - dc[1]) ** 2) ** 0.5 / size
            if score < self.min_iou and dist > self.max_center_dist * 0.5:
                continue
            t = self._tracks[ids[i]]
            oc, nc = self._c(t["box"]), dc
            t["vel"] = (0.6 * t["vel"][0] + 0.4 * (nc[0] - oc[0]), 0.6 * t["vel"][1] + 0.4 * (nc[1] - oc[1]))
            t.update(box=boxes[j].copy(), conf=float(detections.conf[j]), cls=int(detections.cls[j]), lost=0,
                     hits=t["hits"] + 1)
            mt.add(i); md.add(j)
        for i, tid in enumerate(ids):
            if i not in mt:
                self._tracks[tid]["lost"] += 1
        for tid in [k for k, v in self._tracks.items() if v["lost"] > self.max_lost]:
            del self._tracks[tid]
        for j in range(len(boxes)):
            if j not in md:
                self._tracks[self._next] = dict(box=boxes[j].copy(), conf=float(detections.conf[j]),
                                                cls=int(detections.cls[j]), lost=0, hits=1, vel=(0.0, 0.0))
                self._next += 1
        names = self.config.vehicle_classes
        return [Track(k, names.get(v["cls"], str(v["cls"])), v["conf"], tuple(float(x) for x in v["box"]))
                for k, v in self._tracks.items() if v["lost"] == 0 and v["hits"] >= self.min_hits]

    @staticmethod
    def _predict(t: dict) -> list[float]:
        b, (vx, vy), k = t["box"], t["vel"], 1 + t["lost"]
        return [b[0] + vx * k, b[1] + vy * k, b[2] + vx * k, b[3] + vy * k]


def build_tracker(config: AIConfig, frame_rate: int = 30) -> Tracker:
    if config.tracker.lower() == "centroid":
        return CentroidTracker(config)
    return UltralyticsTracker(config, frame_rate)


VehicleTracker = UltralyticsTracker  # backwards-compatible name
