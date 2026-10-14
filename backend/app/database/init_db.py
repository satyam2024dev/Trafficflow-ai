"""Create tables from the ORM models (idempotent) and seed structural defaults (no traffic data)."""
from __future__ import annotations

import logging

from sqlalchemy import select

from ..models import Area, Camera, CountingLine, Zone
from .session import Base, SessionLocal, get_engine

log = logging.getLogger("trafficflow.db")


def create_tables() -> None:
    Base.metadata.create_all(get_engine())


def seed_defaults() -> bool:
    """Mirror of database/seed.sql. Only runs on an empty database."""
    with SessionLocal() as db:
        if db.scalar(select(Area.id).limit(1)) is not None or db.scalar(select(Camera.id).limit(1)) is not None:
            return False
        areas = [Area(name="Area A", description="Main arterial road", latitude=12.9716, longitude=77.5946, hourly_capacity=1200),
                 Area(name="Area B", description="Commercial junction", latitude=12.9352, longitude=77.6245, hourly_capacity=900),
                 Area(name="Area C", description="Residential connector", latitude=12.9784, longitude=77.6408, hourly_capacity=600)]
        db.add_all(areas)
        db.flush()
        cam = Camera(name="Demo Camera 1", location="Demo junction (video file)", area_id=areas[0].id,
                     source_type="video_file", source_url="demo.mp4", latitude=12.9716, longitude=77.5946)
        db.add(cam)
        db.flush()
        db.add(CountingLine(camera_id=cam.id, name="Main line", x1=0.05, y1=0.6, x2=0.95, y2=0.6,
                            direction_ab="northbound", direction_ba="southbound"))
        db.add(Zone(camera_id=cam.id, name="Monitored zone",
                    polygon=[[0.05, 0.45], [0.95, 0.45], [0.95, 0.85], [0.05, 0.85]]))
        db.commit()
        log.info("Seeded default areas and demo camera")
        return True
