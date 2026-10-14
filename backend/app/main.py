from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from .api import areas, cameras, events, health, predictions, reports, traffic, video
from .config import get_settings
from .database.init_db import create_tables, seed_defaults
from .services.processing_manager import processing
from .websocket.manager import manager

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("trafficflow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.bind_loop(asyncio.get_running_loop())
    try:
        if settings.auto_create_tables:
            create_tables()
        if settings.auto_seed:
            seed_defaults()
    except Exception as e:  # keep the API up so /api/health can explain what is wrong
        log.error("Database initialisation failed: %s", e)
    processing.startup()
    settings.video_path.mkdir(parents=True, exist_ok=True)
    yield
    processing.shutdown()


app = FastAPI(title="TrafficFlow AI", version="1.0.0",
              description="AI-powered vehicle flow monitoring and urban traffic analytics", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"])


@app.exception_handler(OperationalError)
async def db_unavailable(_: Request, exc: OperationalError):
    log.error("Database error: %s", exc.__class__.__name__)
    return JSONResponse(status_code=503, content={"detail": "The database is unavailable. Check that PostgreSQL is running and your .env credentials are correct."})


@app.exception_handler(SQLAlchemyError)
async def db_error(_: Request, exc: SQLAlchemyError):
    log.exception("Database error")
    return JSONResponse(status_code=500, content={"detail": "A database error occurred."})


for r in (health.router, cameras.router, areas.router, traffic.router, events.router, reports.router,
          video.router, predictions.router):
    app.include_router(r, prefix="/api")


@app.websocket("/ws/traffic")
async def ws_traffic(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_json({"type": "hello", "processing": sorted(processing.running_ids())})
        while True:
            msg = await ws.receive_text()  # clients send "ping"; this also detects disconnects
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        log.debug("websocket closed with error", exc_info=True)
    finally:
        manager.disconnect(ws)
