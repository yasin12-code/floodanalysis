"""One-time database bootstrap at app startup: PostGIS extension, schema and
sample data. Idempotent — when the schema exists and the areas table has rows,
nothing happens. Runs on the shared pool so the DB_PGBOUNCER prepared-statement
toggle applies (needed for Neon pooled connection strings).

The SQL files and data files are read from the repository next to this module
(paths resolved from __file__, not the working directory), so it also works
inside the Vercel serverless bundle.
"""

import importlib.util
import logging
from pathlib import Path

from app.db import get_pool

logger = logging.getLogger("webgis")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
INIT_DIR = PROJECT_ROOT / "db" / "init"

# Fixed key for pg_advisory_xact_lock: concurrent cold starts (e.g. two Vercel
# instances booting at once) serialise here and only the first one seeds.
SEED_LOCK_KEY = 753_916_021

# 01_extensions.sql is applied inline below (CREATE EXTENSION must precede the
# to_regclass check); 02-04 only run when the schema is missing entirely.
SCHEMA_FILES = ("02_schema.sql", "03_indexes.sql", "04_views.sql")


def _schema_exists(conn) -> bool:
    row = conn.execute("SELECT to_regclass('public.areas')").fetchone()
    return row[0] is not None


def _apply_schema(conn) -> None:
    for filename in SCHEMA_FILES:
        # No parameters bound, so psycopg sends the whole file as one simple
        # query and PostgreSQL executes all statements in it.
        conn.execute((INIT_DIR / filename).read_text(encoding="utf-8"))


def _load_sample_data(conn) -> int:
    # scripts/ is not a package and the backend's sys.path may not include the
    # project root, so load the script module by file path instead.
    path = PROJECT_ROOT / "scripts" / "load_data.py"
    spec = importlib.util.spec_from_file_location("webgis_load_data", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    counts = module.load_data_into(conn)
    return sum(counts.values())


def ensure_seeded() -> bool:
    """Ensure the database has the extension, schema and sample data.

    Returns True when seeding ran, False when the data was already there.
    """
    with get_pool().connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (SEED_LOCK_KEY,))
        conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        if not _schema_exists(conn):
            logger.info("Schema not found - applying db/init SQL files")
            _apply_schema(conn)
        if conn.execute("SELECT count(*) FROM areas").fetchone()[0] > 0:
            return False
        logger.info("Database is empty - loading sample data from %s", DATA_DIR)
        inserted = _load_sample_data(conn)
        logger.info("Seeded database with %d rows", inserted)
        return True
