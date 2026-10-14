"""Safe access to videos: only plain file names inside the configured videos directory."""
from __future__ import annotations

from pathlib import Path

from ..config import get_settings


class VideoFileError(ValueError):
    pass


def list_videos() -> list[dict]:
    s = get_settings()
    d = s.video_path
    if not d.exists():
        return []
    items = []
    for p in sorted(d.iterdir()):
        if p.is_file() and p.suffix.lower() in s.video_extensions:
            items.append({"name": p.name, "size_mb": round(p.stat().st_size / 1_048_576, 2)})
    return items


def resolve_video(name: str) -> Path:
    s = get_settings()
    if not name or Path(name).name != name or name.startswith("."):
        raise VideoFileError("Invalid video file name.")
    path = (s.video_path / name).resolve()
    if s.video_path not in path.parents:
        raise VideoFileError("Video must be inside the configured videos folder.")
    if path.suffix.lower() not in s.video_extensions:
        raise VideoFileError(f"Unsupported video type '{path.suffix}'. Allowed: {', '.join(sorted(s.video_extensions))}")
    if not path.is_file():
        raise VideoFileError(f"Video '{name}' was not found in the server videos folder. "
                             f"Copy it into the /videos directory first.")
    return path
