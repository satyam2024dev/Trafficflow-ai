from ai.counter import LineCounter, LineDef, crossing_direction

W, H = 1000, 800
LINE = LineDef(id=1, name="L", p1=(0.0, 0.5), p2=(1.0, 0.5))  # horizontal at y=400, A->B = left->right


def trk(tid, x, y, vt="car", conf=0.9):
    return {"track_id": tid, "vehicle_type": vt, "confidence": conf, "point": (x, y)}


def run(counter, track_id, path, vt="car"):
    events = []
    for i, (x, y) in enumerate(path):
        events += counter.update([trk(track_id, x, y, vt)], frame_number=i)
    return events


def test_moving_down_counts_once_as_direction_ba():
    c = LineCounter([LINE], (W, H))
    ev = run(c, 17, [(400, 300), (400, 340), (400, 380), (400, 420), (400, 460)])
    assert len(ev) == 1
    assert ev[0].direction == "southbound" and ev[0].track_id == 17 and ev[0].vehicle_type == "car"


def test_moving_up_is_direction_ab():
    c = LineCounter([LINE], (W, H))
    ev = run(c, 5, [(400, 500), (400, 440), (400, 380), (400, 320)])
    assert [e.direction for e in ev] == ["northbound"]


def test_same_vehicle_over_many_frames_counts_once():
    c = LineCounter([LINE], (W, H))
    ev = run(c, 12, [(300, 100 + 20 * i) for i in range(30)])
    assert len(ev) == 1
    assert c.total() == 1


def test_crossing_back_does_not_double_count():
    c = LineCounter([LINE], (W, H))
    ev = run(c, 3, [(400, 300), (400, 450), (400, 300), (400, 450)])
    assert len(ev) == 1


def test_no_count_if_never_reaches_line():
    c = LineCounter([LINE], (W, H))
    assert run(c, 9, [(400, 100), (400, 200), (400, 300), (400, 390)]) == []


def test_first_seen_beyond_line_is_not_counted():
    c = LineCounter([LINE], (W, H))
    assert run(c, 9, [(400, 500), (400, 600), (400, 700)]) == []


def test_crossing_outside_finite_line_extent_is_ignored():
    short = LineDef(id=2, name="short", p1=(0.4, 0.5), p2=(0.6, 0.5))
    c = LineCounter([short], (W, H))
    assert run(c, 1, [(100, 300), (100, 500)]) == []  # x=100 is far left of the line segment
    assert len(run(c, 2, [(500, 300), (500, 500)])) == 1


def test_skipped_frames_big_jump_still_counts():
    c = LineCounter([LINE], (W, H))
    assert len(run(c, 4, [(400, 100), (400, 700)])) == 1


def test_two_vehicles_counted_independently_with_types_and_totals():
    c = LineCounter([LINE], (W, H))
    for i in range(6):
        c.update([trk(1, 200, 300 + 40 * i, "car"), trk(2, 700, 500 - 40 * i, "bus")], i)
    assert c.total() == 2
    assert c.totals_by_type() == {"car": 1, "bus": 1}
    assert c.totals_by_direction() == {"southbound": 1, "northbound": 1}


def test_diagonal_line_direction():
    # diagonal from bottom-left to top-right; A->B
    p, q = (0, 800), (1000, 0)
    assert crossing_direction((200, 200), (800, 700), p, q) in ("ab", "ba")
    assert crossing_direction((200, 200), (800, 700), p, q) != crossing_direction((800, 700), (200, 200), p, q)


def test_multiple_lines_each_count_once():
    l2 = LineDef(id=2, name="L2", p1=(0.0, 0.8), p2=(1.0, 0.8))
    c = LineCounter([LINE, l2], (W, H))
    ev = run(c, 1, [(400, 300 + 40 * i) for i in range(15)])
    assert sorted(e.line_id for e in ev) == [1, 2]


def test_memory_pruned_for_lost_tracks():
    c = LineCounter([LINE], (W, H), max_idle_frames=5)
    run(c, 1, [(400, 300), (400, 450)])
    for i in range(10, 30):
        c.update([trk(99, 10, 10)], i)
    assert 1 not in c._memory
