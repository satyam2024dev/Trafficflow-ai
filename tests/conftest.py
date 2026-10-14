"""Shared pytest setup. Backend tests use a REAL PostgreSQL database (trafficflow_test)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

# Must be set before the app is imported.
os.environ.setdefault("POSTGRES_DB", "trafficflow_test")
os.environ["POSTGRES_DB"] = os.environ.get("TEST_POSTGRES_DB", "trafficflow_test")
os.environ["DATABASE_URL"] = ""   # never let a .env DATABASE_URL point the tests at a real database
os.environ["AUTO_SEED"] = "false"
os.environ["APP_TIMEZONE"] = "Asia/Kolkata"  # +05:30 - proves hourly bucketing is not UTC-only
os.environ["VIDEO_DIR"] = str(ROOT / "tests" / "_videos")
(ROOT / "tests" / "_videos").mkdir(exist_ok=True)
