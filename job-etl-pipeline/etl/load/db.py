"""
db.py — SQLite database connection and schema setup.

Responsibilities:
- Create database connection
- Enable useful SQLite pragmas
- Initialise required ETL tables
- Provide small helper functions for DB access
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


DEFAULT_DB_PATH = "jobs.db"


JOBS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint     TEXT UNIQUE NOT NULL,
    title           TEXT,
    seniority_level TEXT,
    company         TEXT,
    city            TEXT,
    region          TEXT,
    remote_flag     BOOLEAN,
    salary_min      INTEGER,
    salary_max      INTEGER,
    salary_currency TEXT,
    date_posted     DATE,
    source          TEXT,
    url             TEXT,
    description     TEXT,
    status          TEXT DEFAULT 'active',
    first_seen      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


PIPELINE_RUNS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source          TEXT,
    rows_extracted  INTEGER,
    rows_loaded     INTEGER,
    rows_skipped    INTEGER,
    rows_failed     INTEGER,
    duration_secs   REAL
);
"""


INDEXES_SQL = [
    """
    CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint
    ON jobs (fingerprint);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_jobs_source
    ON jobs (source);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_jobs_status
    ON jobs (status);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_jobs_date_posted
    ON jobs (date_posted);
    """,
]


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Create and return a SQLite connection.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        sqlite3.Connection
    """
    db_file = Path(db_path)

    if db_file.parent != Path("."):
        db_file.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Helpful SQLite settings.
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")

    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """
    Initialise all required tables and indexes.
    """
    conn.execute(JOBS_TABLE_SQL)
    conn.execute(PIPELINE_RUNS_TABLE_SQL)

    for index_sql in INDEXES_SQL:
        conn.execute(index_sql)

    conn.commit()


def close_connection(conn: Optional[sqlite3.Connection]) -> None:
    """
    Safely close a SQLite connection.
    """
    if conn is not None:
        conn.close()


def check_db_ready(conn: sqlite3.Connection) -> bool:
    """
    Confirm required tables exist.

    Useful for quick setup validation.
    """
    required_tables = {"jobs", "pipeline_runs"}

    cursor = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table';
        """
    )

    existing_tables = {row["name"] for row in cursor.fetchall()}

    return required_tables.issubset(existing_tables)