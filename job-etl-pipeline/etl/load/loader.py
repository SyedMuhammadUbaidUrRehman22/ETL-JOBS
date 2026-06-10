"""
loader.py — Load transformed job records into SQLite.

Responsibilities:
- Insert new jobs
- Skip duplicates based on fingerprint
- Update last_seen for existing duplicate records
- Log pipeline run metadata
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any


logger = logging.getLogger(__name__)


JOB_INSERT_COLUMNS = [
    "fingerprint",
    "title",
    "seniority_level",
    "company",
    "city",
    "region",
    "remote_flag",
    "salary_min",
    "salary_max",
    "salary_currency",
    "date_posted",
    "source",
    "url",
    "description",
    "status",
]


def fingerprint_exists(conn: sqlite3.Connection, fingerprint: str) -> bool:
    """
    Check whether a job fingerprint already exists in the jobs table.
    """
    cursor = conn.execute(
        """
        SELECT 1
        FROM jobs
        WHERE fingerprint = ?
        LIMIT 1;
        """,
        (fingerprint,),
    )

    return cursor.fetchone() is not None


def update_last_seen(conn: sqlite3.Connection, fingerprint: str) -> None:
    """
    Update last_seen timestamp for an existing job record.
    """
    conn.execute(
        """
        UPDATE jobs
        SET last_seen = CURRENT_TIMESTAMP
        WHERE fingerprint = ?;
        """,
        (fingerprint,),
    )


def insert_job(conn: sqlite3.Connection, job: dict[str, Any]) -> None:
    """
    Insert one job into the jobs table.
    """
    placeholders = ", ".join(["?"] * len(JOB_INSERT_COLUMNS))
    columns = ", ".join(JOB_INSERT_COLUMNS)

    values = [job.get(column) for column in JOB_INSERT_COLUMNS]

    conn.execute(
        f"""
        INSERT INTO jobs ({columns})
        VALUES ({placeholders});
        """,
        values,
    )


def load_jobs(conn: sqlite3.Connection, jobs: list[dict[str, Any]]) -> dict[str, int]:
    """
    Load a batch of jobs into SQLite.

    Duplicate logic:
        - If fingerprint exists:
            update last_seen
            count as skipped
        - Else:
            insert as new row
            count as loaded

    Returns:
        Dictionary of load statistics.
    """
    stats = {
        "rows_loaded": 0,
        "rows_skipped": 0,
        "rows_failed": 0,
    }

    try:
        with conn:
            for job in jobs:
                try:
                    fingerprint = job.get("fingerprint")

                    if not fingerprint:
                        logger.warning(
                            "Skipping job without fingerprint title=%s company=%s",
                            job.get("title"),
                            job.get("company"),
                        )
                        stats["rows_failed"] += 1
                        continue

                    if fingerprint_exists(conn, fingerprint):
                        update_last_seen(conn, fingerprint)
                        stats["rows_skipped"] += 1
                        continue

                    insert_job(conn, job)
                    stats["rows_loaded"] += 1

                except Exception:
                    logger.exception(
                        "Failed to load job title=%s company=%s url=%s",
                        job.get("title"),
                        job.get("company"),
                        job.get("url"),
                    )
                    stats["rows_failed"] += 1

    except sqlite3.DatabaseError:
        logger.exception("Database transaction failed during job loading")
        raise

    return stats


def log_pipeline_run(
    conn: sqlite3.Connection,
    source: str,
    rows_extracted: int,
    rows_loaded: int,
    rows_skipped: int,
    rows_failed: int,
    duration_secs: float,
) -> None:
    """
    Insert one audit record into pipeline_runs.
    """
    conn.execute(
        """
        INSERT INTO pipeline_runs (
            source,
            rows_extracted,
            rows_loaded,
            rows_skipped,
            rows_failed,
            duration_secs
        )
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (
            source,
            rows_extracted,
            rows_loaded,
            rows_skipped,
            rows_failed,
            duration_secs,
        ),
    )

    conn.commit()