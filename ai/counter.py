"""Virtual counting lines.

Geometry convention (image coordinates, y grows downwards)
----------------------------------------------------------
A line runs from A=(x1,y1) to B=(x2,y2).  For a point P we compute

    side(P) = (x2-x1)*(Py-y1) - (y2-y1)*(Px-x1)

* side > 0  -> P is on the RIGHT-hand side when walking from A to B (as seen on screen)
* side < 0  -> P is on the LEFT-hand side

A vehicle that moves from the right-hand side to the left-hand side is reported as `direction_ab`;
the opposite movement is `direction_ba`.  For a horizontal line drawn left->right this means
"moving up the screen" = direction_ab (default label "northbound") and "moving down" = direction_ba
("southbound").  Swap A and B, or the two labels, to change that - no code change needed.

A track is counted AT MOST ONCE per line (even if it later crosses back), which is what prevents
the "same car, four frames, four counts" problem.
"""
from __future__ import annotations

from dataclasses import dataclass, field

Point = tuple[float, float]


@dataclass
class LineDef:
    id: int
    name: str
    p1: Point  # normalised 0..1
    p2: Point
    direction_ab: str = "northbound"
    direction_ba: str = "southbound"


@dataclass
class CountEvent:
    line_id: int
    line_name: str
    track_id: int
    vehicle_type: str
    direction: str
    confidence: float
    frame_number: int
    point: Point


def side_of_line(p: Point, a: Point, b: Point) -> float:
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def segments_intersect(p: Point, q: Point, a: Point, b: Point, eps: float = 1e-9) -> bool:
    """Does motion segment p->q intersect the finite line segment a->b?"""
    d1 = side_of_line(p, a, b)
    d2 = side_of_line(q, a, b)
    if d1 * d2 > 0:
        return False
    d3 = side_of_line(a, p, q)
    d4 = side_of_line(b, p, q)
    if d3 * d4 > eps:
        return False
    # Degenerate (collinear) motion along the line is not a crossing
    return not (abs(d1) < eps and abs(d2) < eps)


def crossing_direction(prev: Point, cur: Point, a: Point, b: Point) -> str | None:
    """Return 'ab' / 'ba' if prev->cur crosses a->b, else None."""
    if not segments_intersect(prev, cur, a, b):
        return None
    s0 = side_of_line(prev, a, b)
    s1 = side_of_line(cur, a, b)
    if s0 > 0 and s1 <= 0:
        return "ab"  # right-hand -> left-hand
    if s0 < 0 and s1 >= 0:
        return "ba"
    if s0 == 0 and s1 < 0:
        return "ab"
    if s0 == 0 and s1 > 0:
        return "ba"
    return None


@dataclass
class _TrackMemory:
    last_point: Point
    last_seen_frame: int
    last_side: dict[int, float] = field(default_factory=dict)  # line_id -> last non-zero side


class LineCounter:
    def __init__(self, lines: list[LineDef], frame_size: tuple[int, int], max_idle_frames: int = 300):
        self.width, self.height = frame_size
        self.lines = lines
        self.max_idle_frames = max_idle_frames
        self._abs = {
            ln.id: ((ln.p1[0] * self.width, ln.p1[1] * self.height), (ln.p2[0] * self.width, ln.p2[1] * self.height))
            for ln in lines
        }
        self._memory: dict[int, _TrackMemory] = {}
        self._counted: set[tuple[int, int]] = set()  # (line_id, track_id)
        # totals[line_id][vehicle_type][direction] = n
        self.totals: dict[int, dict[str, dict[str, int]]] = {ln.id: {} for ln in lines}

    # ------------------------------------------------------------------
    def update(self, tracks: list[dict], frame_number: int) -> list[CountEvent]:
        """tracks: [{'track_id', 'vehicle_type', 'confidence', 'point': (x, y)}] in pixel coords."""
        events: list[CountEvent] = []
        for t in tracks:
            tid = t["track_id"]
            cur = t["point"]
            mem = self._memory.get(tid)
            if mem is None:
                mem = _TrackMemory(last_point=cur, last_seen_frame=frame_number)
                for ln in self.lines:
                    a, b = self._abs[ln.id]
                    s = side_of_line(cur, a, b)
                    if s != 0:
                        mem.last_side[ln.id] = s
                self._memory[tid] = mem
                continue

            for ln in self.lines:
                key = (ln.id, tid)
                a, b = self._abs[ln.id]
                if key not in self._counted:
                    d = crossing_direction(mem.last_point, cur, a, b)
                    if d is not None:
                        self._counted.add(key)
                        direction = ln.direction_ab if d == "ab" else ln.direction_ba
                        by_type = self.totals[ln.id].setdefault(t["vehicle_type"], {})
                        by_type[direction] = by_type.get(direction, 0) + 1
                        events.append(
                            CountEvent(ln.id, ln.name, tid, t["vehicle_type"], direction,
                                       float(t.get("confidence", 0.0)), frame_number, cur)
                        )
                s = side_of_line(cur, a, b)
                if s != 0:
                    mem.last_side[ln.id] = s
            mem.last_point = cur
            mem.last_seen_frame = frame_number

        self._prune(frame_number)
        return events

    def _prune(self, frame_number: int) -> None:
        stale = [tid for tid, m in self._memory.items() if frame_number - m.last_seen_frame > self.max_idle_frames]
        if not stale:
            return
        for tid in stale:
            del self._memory[tid]
        stale_set = set(stale)
        # Tracker IDs are never reused, so forgetting long-gone tracks is safe and bounds memory.
        self._counted = {k for k in self._counted if k[1] not in stale_set}

    # ------------------------------------------------------------------
    def total(self, line_id: int | None = None) -> int:
        ids = [line_id] if line_id is not None else list(self.totals)
        return sum(n for lid in ids for d in self.totals.get(lid, {}).values() for n in d.values())

    def totals_by_type(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for per_line in self.totals.values():
            for vt, dirs in per_line.items():
                out[vt] = out.get(vt, 0) + sum(dirs.values())
        return out

    def totals_by_direction(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for per_line in self.totals.values():
            for dirs in per_line.values():
                for d, n in dirs.items():
                    out[d] = out.get(d, 0) + n
        return out
