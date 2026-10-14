from ai.zones import ZoneDef, ZoneMonitor, point_in_polygon, rect_to_polygon

SQUARE = rect_to_polygon(0, 0, 10, 10)


def test_point_in_polygon_basic():
    assert point_in_polygon((5, 5), SQUARE)
    assert not point_in_polygon((15, 5), SQUARE)
    assert point_in_polygon((0, 5), SQUARE)  # boundary counts as inside


def test_concave_polygon():
    L = [(0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10)]
    assert point_in_polygon((2, 8), L)
    assert not point_in_polygon((8, 8), L)


def mk(grace=3):
    z = ZoneDef(1, "A", [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)])
    return ZoneMonitor([z], (100, 100), exit_grace_frames=grace)


def t(tid, x, y):
    return {"track_id": tid, "vehicle_type": "car", "point": (x, y)}


def test_enter_inside_exit():
    m = mk()
    assert m.update([t(1, 10, 50)], 0) == []
    ev = m.update([t(1, 50, 50)], 1)
    assert [e.event_type for e in ev] == ["enter"] and m.occupancy() == {1: 1}
    assert m.update([t(1, 55, 50)], 2) == []
    ev = m.update([t(1, 90, 50)], 3)
    assert [e.event_type for e in ev] == ["exit"] and m.occupancy() == {1: 0}


def test_brief_dropout_does_not_cause_exit():
    m = mk(grace=3)
    m.update([t(1, 50, 50)], 0)
    for f in (1, 2, 3):
        assert m.update([], f) == []
    assert m.occupancy() == {1: 1}
    assert m.update([t(1, 52, 50)], 4) == []  # no second 'enter'


def test_long_dropout_exits_once():
    m = mk(grace=2)
    m.update([t(1, 50, 50)], 0)
    evs = []
    for f in range(1, 6):
        evs += m.update([], f)
    assert [e.event_type for e in evs] == ["exit"]


def test_multiple_vehicles_occupancy():
    m = mk()
    m.update([t(1, 50, 50), t(2, 60, 60), t(3, 5, 5)], 0)
    assert m.occupancy() == {1: 2}
    assert m.occupancy_by_type() == {1: {"car": 2}}
