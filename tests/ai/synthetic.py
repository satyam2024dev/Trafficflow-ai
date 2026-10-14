"""TEST HELPERS ONLY - not used by the application.

make_video(): renders a synthetic top-down road with coloured boxes as vehicles (known ground truth).
ColorBlobDetector: a real (but trivial) detector for that synthetic scene, standing in for YOLO so the
rest of the pipeline (video -> tracking -> counting -> DB -> WebSocket) can be tested without PyTorch.
"""
from __future__ import annotations

import cv2
import numpy as np

from ai.detector import Detections

W, H, FPS = 640, 480, 25
# BGR colour -> (COCO class id, size)
VEHICLES = {"car": ((0, 0, 255), 2, (50, 30)), "bus": ((0, 255, 0), 5, (90, 36)), "truck": ((255, 0, 0), 7, (70, 34))}
COLOR_TO_CLS = {v[0]: v[1] for v in VEHICLES.values()}


def make_video(path: str, plan: list[dict], frames: int = 150) -> None:
    """plan items: {type, x, y0, y1, start, end} - vehicle moves linearly y0->y1 between frames start..end."""
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for f in range(frames):
        img = np.full((H, W, 3), 90, np.uint8)
        cv2.rectangle(img, (0, 100), (W, 420), (60, 60, 60), -1)
        for v in plan:
            if v["start"] <= f <= v["end"]:
                t = (f - v["start"]) / max(1, v["end"] - v["start"])
                y = v["y0"] + (v["y1"] - v["y0"]) * t
                col, _, (w, h) = VEHICLES[v["type"]]
                cv2.rectangle(img, (int(v["x"] - w / 2), int(y - h / 2)), (int(v["x"] + w / 2), int(y + h / 2)), col, -1)
        out.write(img)
    out.release()


class ColorBlobDetector:
    """Duck-typed VehicleDetector."""
    def __init__(self, *_a, **_k):
        self.loaded = False

    def load(self):
        self.loaded = True

    def detect(self, frame: np.ndarray) -> Detections:
        boxes, confs, clss = [], [], []
        for col, cls_id in COLOR_TO_CLS.items():
            mask = cv2.inRange(frame, np.array(col) - 25 if col else 0, np.array(col) + 25)
            mask = cv2.inRange(frame, np.clip(np.array(col) - 40, 0, 255), np.clip(np.array(col) + 40, 0, 255))
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in cnts:
                x, y, w, h = cv2.boundingRect(c)
                if w * h > 300:
                    boxes.append([x, y, x + w, y + h]); confs.append(0.9); clss.append(cls_id)
        if not boxes:
            return Detections(np.zeros((0, 4), np.float32), np.zeros(0, np.float32), np.zeros(0, np.float32))
        return Detections(np.array(boxes, np.float32), np.array(confs, np.float32), np.array(clss, np.float32))
