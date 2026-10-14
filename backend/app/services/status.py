"""Traffic level classification shared by the map, dashboard and prediction module."""
from __future__ import annotations


def level_from_ratio(ratio: float) -> str:
    if ratio < 0.40:
        return "LOW"
    if ratio < 0.70:
        return "MODERATE"
    if ratio < 0.90:
        return "HIGH"
    return "CRITICAL"


def level_from_count(vehicles_per_hour: float, hourly_capacity: int) -> str:
    return level_from_ratio(vehicles_per_hour / max(hourly_capacity, 1))
