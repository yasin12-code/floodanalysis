"""psycopg 3 connection pool shared by all routers."""

import os

from psycopg_pool import ConnectionPool

pool: ConnectionPool | None = None


def init_pool(database_url: str) -> None:
    global pool
    # Extra arguments forwarded to psycopg.connect():
    # - Neon's pooled endpoint runs PgBouncer in transaction mode, which cannot
    #   handle psycopg's prepared statements. Auto-detect the "-pooler" host
    #   and also honour the explicit DB_PGBOUNCER=1 toggle.
    # - A connect timeout makes unreachable databases fail fast instead of
    #   burning the serverless function's time budget on a hanging attempt.
    kwargs = {"connect_timeout": 10}
    if os.environ.get("DB_PGBOUNCER") == "1" or "-pooler" in database_url:
        kwargs["prepare_threshold"] = None
    pool = ConnectionPool(database_url, min_size=1, max_size=10, open=True, kwargs=kwargs)


def close_pool() -> None:
    global pool
    if pool is not None:
        pool.close()
        pool = None


def get_pool() -> ConnectionPool:
    if pool is None:
        raise RuntimeError("Connection pool is not initialised")
    return pool
