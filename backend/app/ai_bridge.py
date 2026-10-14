"""Tiny helper so the API can report AI-model availability without importing torch at startup."""
from __future__ import annotations

import sys

from .config import REPO_ROOT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def model_status() -> dict:
    from ai.config import AIConfig
    cfg = AIConfig()
    p = cfg.resolved_model_path()
    return {"ok": p.exists(), "path": str(p.relative_to(REPO_ROOT)) if REPO_ROOT in p.parents else p.name,
            "message": "ok" if p.exists() else "Model file missing - run: python scripts/download_model.py",
            "classes": list(cfg.vehicle_classes.values()), "confidence_threshold": cfg.confidence_threshold,
            "tracker": cfg.tracker, "device": cfg.device}
