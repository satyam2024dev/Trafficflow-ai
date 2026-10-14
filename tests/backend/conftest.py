import pytest
from sqlalchemy import text

try:
    from app.database.session import Base, SessionLocal, get_engine
    from app import models  # noqa: F401
    get_engine().connect().close()
    DB_OK = True
except Exception as e:  # pragma: no cover
    DB_OK = False
    DB_ERR = str(e)


def pytest_collection_modifyitems(config, items):
    if not DB_OK:
        skip = pytest.mark.skip(reason="PostgreSQL test database not reachable")
        for it in items:
            it.add_marker(skip)


@pytest.fixture(scope="session", autouse=True)
def schema():
    if not DB_OK:
        yield
        return
    assert get_engine().url.database.endswith("_test"), "Refusing to run destructive tests on a non-test database"
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    yield


@pytest.fixture(autouse=True)
def clean():
    if DB_OK:
        with get_engine().begin() as c:
            c.execute(text("TRUNCATE vehicle_events, zone_events, traffic_summaries, counting_lines, zones, cameras, areas RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def world(db):
    """Two areas, three cameras."""
    from app.models import Area, Camera, CountingLine
    a1 = Area(name="Area A", hourly_capacity=1000, latitude=12.97, longitude=77.59)
    a2 = Area(name="Area B", hourly_capacity=500, latitude=12.93, longitude=77.62)
    db.add_all([a1, a2]); db.flush()
    c1 = Camera(name="Cam 1", area_id=a1.id, source_url="x.mp4")
    c2 = Camera(name="Cam 2", area_id=a1.id, source_url="y.mp4")
    c3 = Camera(name="Cam 3", area_id=a2.id, source_url="z.mp4")
    db.add_all([c1, c2, c3]); db.flush()
    db.add(CountingLine(camera_id=c1.id, name="L", x1=0, y1=.5, x2=1, y2=.5))
    db.commit()
    return {"a1": a1, "a2": a2, "c1": c1, "c2": c2, "c3": c3}


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
