from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..config import get_settings


def tz() -> ZoneInfo:
    try:
        return ZoneInfo(get_settings().app_timezone)
    except Exception:  # invalid name in .env -> fall back safely instead of crashing
        return ZoneInfo("UTC")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def floor_hour_local(ts: datetime) -> datetime:
    """Start of the hour containing ts, expressed in the app timezone (timezone-aware)."""
    return ts.astimezone(tz()).replace(minute=0, second=0, microsecond=0)


def start_of_today() -> datetime:
    return now_utc().astimezone(tz()).replace(hour=0, minute=0, second=0, microsecond=0)


def start_of_day(d) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=tz())


def end_of_day_exclusive(d) -> datetime:
    return start_of_day(d) + timedelta(days=1)
