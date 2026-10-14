"""Polygon / rectangle monitoring zones: who entered, who left, who is inside right now.

Pure Python (no OpenCV/NumPy) so it is trivially unit-testable.
Polygons are given in *normalised* (0..1) coordinates and scaled to the frame at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field

Point = tuple[float, float]


def point_in_polygon(point: Point, polygon: list[Point]) -> bool:
    """Ray-casting point-in-polygon test (boundary points count as inside)."""
    x, y = point
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        # On-edge check
        cross = (x - xi) * (yj - yi) - (y - yi) * (xj - xi)
        if abs(cross) < 1e-9 and min(xi, xj) - 1e-9 <= x <= max(xi, xj) + 1e-9 and min(yi, yj) - 1e-9 <= y <= max(yi, yj) + 1e-9:
            return True
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def rect_to_polygon(x1: float, y1: float, x2: float, y2: float) -> list[Point]:
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


@dataclass
class ZoneDef:
    id: int
    name: str
    polygon: list[Point]  # normalised 0..1

    def scaled(self, width: int, height: int) -> list[Point]:
        return [(x * width, y * height) for x, y in self.polygon]


@dataclass
class ZoneEvent:
    zone_id: int
    track_id: int
    vehicle_type: str
    event_type: str  # "enter" | "exit"
    frame_number: int


@dataclass
class _ZoneState:
    # track_id -> frames since last seen (0 while visible)
    inside: dict[int, int] = field(default_factory=dict)
    types: dict[int, str] = field(default_factory=dict)


class ZoneMonitor:
    """Tracks occupancy of every zone.

    A track that disappears while inside a zone is declared 'exited' only after `exit_grace_frames`
    processed frames without being seen, so a brief missed detection does not create a false
    exit + re-entry pair.
    """

    def __init__(self, zones: list[ZoneDef], frame_size: tuple[int, int], exit_grace_frames: int = 10):
        self.zones = zones
        self.width, self.height = frame_size
        self.exit_grace_frames = exit_grace_frames
        self._polys = {z.id: z.scaled(self.width, self.height) for z in zones}
        self._state = {z.id: _ZoneState() for z in zones}

    def update(self, tracks: list[dict], frame_number: int) -> list[ZoneEvent]:
        """tracks: [{'track_id', 'vehicle_type', 'point': (x, y)}] in pixel coordinates."""
        events: list[ZoneEvent] = []
        seen_ids = {t["track_id"] for t in tracks}
        for zone in self.zones:
            st = self._state[zone.id]
            poly = self._polys[zone.id]
            for t in tracks:
                tid = t["track_id"]
                if point_in_polygon(t["point"], poly):
                    if tid not in st.inside:
                        events.append(ZoneEvent(zone.id, tid, t["vehicle_type"], "enter", frame_number))
                        st.types[tid] = t["vehicle_type"]
                    st.inside[tid] = 0
                elif tid in st.inside:
                    # visible but outside the polygon -> left immediately
                    events.append(ZoneEvent(zone.id, tid, st.types.get(tid, t["vehicle_type"]), "exit", frame_number))
                    del st.inside[tid]
                    st.types.pop(tid, None)
            # tracks inside that were not seen this frame
            for tid in list(st.inside):
                if tid in seen_ids:
                    continue
                st.inside[tid] += 1
                if st.inside[tid] > self.exit_grace_frames:
                    events.append(ZoneEvent(zone.id, tid, st.types.get(tid, "vehicle"), "exit", frame_number))
                    del st.inside[tid]
                    st.types.pop(tid, None)
        return events

    def occupancy(self) -> dict[int, int]:
        """zone_id -> number of vehicles currently inside."""
        return {zid: len(st.inside) for zid, st in self._state.items()}

    def occupancy_by_type(self) -> dict[int, dict[str, int]]:
        out: dict[int, dict[str, int]] = {}
        for zid, st in self._state.items():
            counts: dict[str, int] = {}
            for tid in st.inside:
                vt = st.types.get(tid, "vehicle")
                counts[vt] = counts.get(vt, 0) + 1
            out[zid] = counts
        return out
