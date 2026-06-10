"""
exporter.py — Export loaded SQLite job data to files.

Responsibilities:
- Export clean jobs from SQLite to CSV
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd


logger = logging.getLogger(__name__)


DEFAULT_EXPORT_COLUMNS = [
    "id",
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
    "first_seen",
    "last_seen",
]


def export_jobs_to_csv(
    conn: sqlite3.Connection,
    output_path: str = "output/jobs_clean.csv",
    include_statuses: tuple[str, ...] = ("active", "incomplete"),
) -> int:
    """
    Export clean jobs from SQLite to CSV.

    Args:
        conn: SQLite connection.
        output_path: Destination CSV path.
        include_statuses: Job statuses to include in export.

    Returns:
        Number of rows exported.
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    placeholders = ", ".join(["?"] * len(include_statuses))
    columns = ", ".join(DEFAULT_EXPORT_COLUMNS)

    query = f"""
        SELECT {columns}
        FROM jobs
        WHERE status IN ({placeholders})
        ORDER BY last_seen DESC, id DESC;
    """

    df = pd.read_sql_query(
        query,
        conn,
        params=include_statuses,
    )

    df.to_csv(output_file, index=False, encoding="utf-8")

    logger.info(
        "Exported jobs CSV rows=%d path=%s",
        len(df),
        output_file,
    )

    return len(df)