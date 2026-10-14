"""Vehicle detection with Ultralytics YOLO.  Detection only - tracking lives in tracker.py."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from .config import AIConfig

log = logging.getLogger("trafficflow.detector")


class ModelNotFoundError(RuntimeError):
    pass


@dataclass
class Detections:
    """Raw detections for one frame (pixel coordinates).  Shaped like ultralytics `Boxes` so the
    ultralytics trackers can consume it directly."""
    xyxy: np.ndarray   # (N, 4)
    conf: np.ndarray   # (N,)
    cls: np.ndarray    # (N,)

    @property
    def xywh(self) -> np.ndarray:
        if len(self.xyxy) == 0:
            return np.zeros((0, 4), dtype=np.float32)
        x1, y1, x2, y2 = self.xyxy.T
        return np.stack([(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1], axis=1).astype(np.float32)

    def __len__(self) -> int:
        return len(self.conf)

    def __getitem__(self, idx):
        return Detections(self.xyxy[idx], self.conf[idx], self.cls[idx])


class VehicleDetector:
    def __init__(self, config: AIConfig | None = None):
        self.config = config or AIConfig()
        self._model = None

    def load(self) -> None:
        path = self.config.resolved_model_path()
        if not path.exists():
            raise ModelNotFoundError(
                f"YOLO model not found at '{path}'. Run `python scripts/download_model.py` "
                f"or set YOLO_MODEL in your .env file."
            )
        try:
            from ultralytics import YOLO
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("ultralytics is not installed: pip install ultralytics") from e
        log.info("Loading YOLO model %s on %s", path, self.config.device)
        self._model = YOLO(str(path))

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def detect(self, frame: np.ndarray) -> Detections:
        """Run the model on one BGR frame; keep only configured vehicle classes above the threshold."""
        if self._model is None:
            self.load()
        res = self._model.predict(
            frame,
            conf=self.config.confidence_threshold,
            iou=self.config.iou_threshold,
            classes=list(self.config.vehicle_classes.keys()),
            imgsz=self.config.inference_size,
            device=self.config.device,
            verbose=False,
        )[0]
        b = res.boxes
        if b is None or len(b) == 0:
            return Detections(np.zeros((0, 4), np.float32), np.zeros(0, np.float32), np.zeros(0, np.float32))
        return Detections(b.xyxy.cpu().numpy(), b.conf.cpu().numpy(), b.cls.cpu().numpy())
