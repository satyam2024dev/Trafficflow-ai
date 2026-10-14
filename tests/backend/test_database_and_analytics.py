from datetime import timedelta

from sqlalchemy import func, select, text

from app.models import TrafficSummary, VehicleEvent
from app.services import analytics as an
from app.services.events import rebuild_summaries, record_vehicle_event
from app.utils.timeutil import start_of_today, tz


def add(db, cam, vt="car", direction="northbound", ts=None, track=1, conf=0.9):
    return record_vehicle_event(db, camera=cam, line_id=None, track_id=track, vehicle_type=vt,
                                direction=direction, confidence=conf, frame_number=1, timestamp=ts)


def test_record_event_persists_and_rolls_up(db, world):
    t0 = start_of_today() + timedelta(minutes=10)
    for i in range(3):
        add(db, world["c1"], ts=t0 + timedelta(minutes=i), track=i)
    assert db.scalar(select(func.count()).select_from(VehicleEvent)) == 3
    s = db.scalars(select(TrafficSummary)).all()
    assert len(s) == 1 and s[0].vehicle_count == 3
    assert s[0].bucket_start == start_of_today()  # hour bucket is in the app's local timezone (+05:30)


def test_summaries_match_events_and_rebuild_is_identical(db, world):
    base = start_of_today() - timedelta(days=1)
    for h, vt in [(1, "car"), (1, "bus"), (2, "car"), (14, "truck")]:
        add(db, world["c1"], vt=vt, ts=base + timedelta(hours=h, minutes=5))
    before = sorted((s.bucket_start, s.vehicle_type, s.vehicle_count) for s in db.scalars(select(TrafficSummary)))
    n = rebuild_summaries(db)
    after = sorted((s.bucket_start, s.vehicle_type, s.vehicle_count) for s in db.scalars(select(TrafficSummary)))
    assert n == 4 and before == after
    assert db.scalar(select(func.sum(TrafficSummary.vehicle_count))) == db.scalar(select(func.count()).select_from(VehicleEvent))


def test_indexes_exist(db):
    names = {r[0] for r in db.execute(text("select indexname from pg_indexes where tablename='vehicle_events'"))}
    assert {"ix_events_timestamp", "ix_events_camera", "ix_events_area", "ix_events_type"} <= names or \
           any("timestamp" in n for n in names)


def test_today_totals_and_types(db, world):
    t = start_of_today() + timedelta(minutes=5)
    for vt, n in [("car", 5), ("motorcycle", 3), ("bus", 2), ("truck", 1)]:
        for i in range(n):
            add(db, world["c1"], vt=vt, ts=t, track=i)
    r = an.today_summary(db)
    assert r["total"] == 11 and r["by_type"] == {"car": 5, "motorcycle": 3, "bus": 2, "truck": 1}
    assert [x["vehicle_type"] for x in an.by_type(db, an.Filters())][0] == "car"


def test_by_area_and_by_camera(db, world):
    t = start_of_today() + timedelta(minutes=5)
    for _ in range(4): add(db, world["c1"], ts=t)
    for _ in range(2): add(db, world["c2"], vt="bus", ts=t)
    for _ in range(3): add(db, world["c3"], vt="truck", ts=t)
    areas = {a["area_name"]: a for a in an.by_area(db, an.Filters())}
    assert areas["Area A"]["total"] == 6 and areas["Area A"]["car"] == 4 and areas["Area A"]["bus"] == 2
    assert areas["Area B"]["total"] == 3 and areas["Area B"]["truck"] == 3
    cams = {c["camera_name"]: c["total"] for c in an.by_camera(db, an.Filters())}
    assert cams == {"Cam 1": 4, "Cam 2": 2, "Cam 3": 3}
    assert an.today_summary(db, an.Filters(area_id=world["a2"].id))["total"] == 3


def test_direction_breakdown(db, world):
    t = start_of_today() + timedelta(minutes=5)
    for _ in range(3): add(db, world["c1"], direction="northbound", ts=t)
    add(db, world["c1"], direction="southbound", ts=t)
    assert {d["direction"]: d["count"] for d in an.by_direction(db, an.Filters())} == {"northbound": 3, "southbound": 1}


def test_hourly_fills_gaps_and_uses_local_hours(db, world):
    t0 = start_of_today()
    add(db, world["c1"], ts=t0 + timedelta(minutes=20))
    add(db, world["c1"], ts=t0 + timedelta(hours=1, minutes=40))
    add(db, world["c1"], ts=t0 + timedelta(hours=1, minutes=45), vt="bus")
    h = an.hourly(db, an.Filters(start=t0, end=t0 + timedelta(hours=4)))
    assert [x["count"] for x in h] == [1, 2, 0, 0]
    assert [x["label"] for x in h] == ["00:00", "01:00", "02:00", "03:00"]
    assert h[1]["bus"] == 1


def test_daily_weekly_monthly_and_peak(db, world):
    t0 = start_of_today()
    for d in (0, 1, 2):
        for i in range(d + 1):
            add(db, world["c1"], ts=t0 - timedelta(days=d) + timedelta(hours=9, minutes=i))
    for i in range(5):
        add(db, world["c1"], ts=t0 - timedelta(days=1) + timedelta(hours=18, minutes=i), vt="truck")
    daily = an.daily(db, an.Filters(), days=3)
    assert [d["count"] for d in daily] == [3, 7, 1]
    assert sum(d["count"] for d in an.weekly(db, an.Filters(), weeks=8)) >= 1
    assert sum(d["count"] for d in an.monthly(db, an.Filters(), months=3)) == 11
    peaks = an.peak_hours(db, an.Filters())
    assert peaks["peak_hours"][0]["hour"] in (9, 18)
    assert len(peaks["hours"]) == 24


def test_trends_no_baseline(db, world):
    add(db, world["c1"], ts=start_of_today() + timedelta(minutes=5))
    t = an.trends(db, an.Filters())
    assert t["last_7_days"] == 1 and t["previous_7_days"] == 0 and t["direction"] == "no_baseline"


def test_live_levels(db, world):
    from app.utils.timeutil import now_utc
    for i in range(30):
        add(db, world["c3"], ts=now_utc(), track=i)   # 30 in 15 min -> 120/h vs capacity 500
    lv = {x["camera_name"]: x for x in an.live_levels(db, set())}
    assert lv["Cam 3"]["traffic_level"] == "LOW" and lv["Cam 3"]["estimated_per_hour"] == 120
    assert lv["Cam 1"]["traffic_level"] == "NO_DATA"
    for i in range(100):
        add(db, world["c3"], ts=now_utc(), track=100 + i)
    assert {x["camera_name"]: x for x in an.live_levels(db, set())}["Cam 3"]["traffic_level"] == "CRITICAL"
