"""Shared fixtures: real PostGIS database, reseeded sample data, TestClient.

The tests are integration tests: they hit a real PostGIS instance (DATABASE_URL,
defaulting to the local non-Docker setup from the README). The sample data is
reloaded once per session with scripts/load_data.py (idempotent).
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/webgis")

import psycopg
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def seeded_database():
    from scripts.load_data import load_features
    load_features(os.environ["DATABASE_URL"])


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def db_conn():
    """Direct psycopg connection for setup/teardown helpers in tests."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        yield conn


@pytest.fixture()
def cleanup_test_rows(db_conn):
    """Delete any rows created by the test that ran (name-prefixed)."""
    yield
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM shelters WHERE name LIKE 'TEST-%'")
        cur.execute("DELETE FROM flood_reports WHERE description = 'pytest cleanup marker'")
    db_conn.commit()


def load_test_points():
    import json
    path = ROOT_DIR / "data" / "test_points.json"
    return json.load(open(path, encoding="utf-8"))["points"]
