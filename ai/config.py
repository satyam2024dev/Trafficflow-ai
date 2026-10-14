"""Central configuration for the AI pipeline. Everything is overridable via environment variables
(or the repo-root / backend .env file), so no source edits are needed to tune behaviour."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional for the AI package on its own
        return
    for p in (REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"):
        if p.exists():
            load_dotenv(p, override=False)


_load_dotenv()


def _parse_classes(raw: str) -> dict[int, str]:
    """'2:car,3:motorcycle' -> {2: 'car', 3: 'motorcycle'}"""
    out: dict[int, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        cid, _, name = part.partition(":")
        out[int(cid)] = name.strip()
    return out


@dataclass
class AIConfig:
    model_path: str = field(default_factory=lambda: os.getenv("YOLO_MODEL", "ai/models/yolo11n.pt"))
    # COCO ids. Change YOLO_VEHICLE_CLASSES to use a custom model, e.g. "0:car,1:rickshaw".
    vehicle_classes: dict[int, str] = field(
        default_factory=lambda: _parse_classes(
            os.getenv("YOLO_VEHICLE_CLASSES", "2:car,3:motorcycle,5:bus,7:truck")
        )
    )
    confidence_threshold: float = field(default_factory=lambda: float(os.getenv("CONFIDENCE_THRESHOLD", "0.35")))
    iou_threshold: float = field(default_factory=lambda: float(os.getenv("IOU_THRESHOLD", "0.5")))
    device: str = field(default_factory=lambda: os.getenv("YOLO_DEVICE", "cpu"))  # "cpu", "0", "cuda:0"
    inference_size: int = field(default_factory=lambda: int(os.getenv("YOLO_IMGSZ", "640")))

    tracker: str = field(default_factory=lambda: os.getenv("TRACKER", "bytetrack"))  # bytetrack | botsort
    process_width: int = field(default_factory=lambda: int(os.getenv("PROCESS_WIDTH", "960")))
    frame_skip: int = field(default_factory=lambda: int(os.getenv("FRAME_SKIP", "2")))  # run AI every Nth frame
    realtime_playback: bool = field(default_factory=lambda: os.getenv("REALTIME_PLAYBACK", "true").lower() == "true")
    loop_video: bool = field(default_factory=lambda: os.getenv("LOOP_VIDEO", "false").lower() == "true")
    jpeg_quality: int = field(default_factory=lambda: int(os.getenv("STREAM_JPEG_QUALITY", "70")))
    reference_point: str = field(default_factory=lambda: os.getenv("REFERENCE_POINT", "center"))  # center|bottom_center
    zone_exit_grace_frames: int = field(default_factory=lambda: int(os.getenv("ZONE_EXIT_GRACE_FRAMES", "10")))

    def resolved_model_path(self) -> Path:
        p = Path(self.model_path)
        return p if p.is_absolute() else REPO_ROOT / p
