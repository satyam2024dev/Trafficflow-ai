from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SourceType = Literal["video_file", "webcam", "rtsp"]
CameraStatus = Literal["offline", "online", "processing", "error", "inactive"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- areas
class AreaBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    hourly_capacity: int = Field(default=1200, gt=0, le=100000)


class AreaCreate(AreaBase):
    pass


class AreaUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    hourly_capacity: int | None = Field(default=None, gt=0, le=100000)


class AreaOut(AreaBase, ORM):
    id: int
    created_at: datetime


# ---------------------------------------------------------------- cameras
class CameraBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=255)
    area_id: int | None = None
    source_type: SourceType = "video_file"
    source_url: str = Field(min_length=1, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def check_source(self):
        s = self.source_url.strip()
        if self.source_type == "rtsp":
            if not s.lower().startswith(("rtsp://", "rtsps://")):
                raise ValueError("RTSP sources must start with rtsp:// or rtsps://")
        elif self.source_type == "webcam":
            if not s.isdigit() or int(s) > 20:
                raise ValueError("Webcam source must be a device index such as 0 or 1")
        else:  # video_file: a bare file name inside the configured videos folder
            if "/" in s or "\\" in s or ".." in s or ":" in s:
                raise ValueError("Video files must be selected by file name from the server's videos folder")
        self.source_url = s
        return self


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=255)
    area_id: int | None = None
    source_type: SourceType | None = None
    source_url: str | None = Field(default=None, min_length=1, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_active: bool | None = None


class CameraOut(ORM):
    id: int
    name: str
    location: str | None
    area_id: int | None
    area_name: str | None = None
    source_type: str
    source_url: str
    status: str
    latitude: float | None
    longitude: float | None
    is_active: bool
    last_error: str | None
    created_at: datetime
    processing: bool = False


# ---------------------------------------------------------------- lines / zones
class LineBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)
    x2: float = Field(ge=0, le=1)
    y2: float = Field(ge=0, le=1)
    direction_ab: str = Field(default="northbound", min_length=1, max_length=40)
    direction_ba: str = Field(default="southbound", min_length=1, max_length=40)

    @model_validator(mode="after")
    def not_a_point(self):
        if abs(self.x1 - self.x2) < 1e-6 and abs(self.y1 - self.y2) < 1e-6:
            raise ValueError("A counting line needs two different points")
        return self


class LineCreate(LineBase):
    pass


class LineOut(LineBase, ORM):
    id: int
    camera_id: int
    is_active: bool


class ZoneBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    polygon: list[tuple[float, float]] = Field(min_length=3, max_length=50)

    @field_validator("polygon")
    @classmethod
    def normalised(cls, v):
        for x, y in v:
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise ValueError("Polygon points must be normalised to the 0..1 range")
        return v


class ZoneCreate(ZoneBase):
    pass


class ZoneOut(ORM):
    id: int
    camera_id: int
    name: str
    polygon: list
    is_active: bool


# ---------------------------------------------------------------- events
class VehicleEventOut(ORM):
    id: int
    camera_id: int
    camera_name: str | None = None
    area_id: int | None
    area_name: str | None = None
    track_id: int
    vehicle_type: str
    direction: str
    confidence: float
    timestamp: datetime
    frame_number: int | None
    speed_kmh: float | None


class EventPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[VehicleEventOut]


# ---------------------------------------------------------------- video control
class VideoStartRequest(BaseModel):
    camera_id: int = Field(gt=0)


class VideoStopRequest(BaseModel):
    camera_id: int = Field(gt=0)
