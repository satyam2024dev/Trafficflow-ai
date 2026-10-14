from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ..ai_bridge import model_status
from ..database.session import SessionLocal
from ..services.processing_manager import processing
from ..websocket.manager import manager

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    db_ok, db_msg = True, "ok"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as e:  # report, don't crash
        db_ok, db_msg = False, f"{type(e).__name__}: database unavailable"
    model = model_status()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": {"ok": db_ok, "message": db_msg},
        "model": model,
        "processing_cameras": sorted(processing.running_ids()),
        "websocket_clients": manager.client_count,
    }
