"""
main.py — Pipeline entry point.

Current stage:
- Setup logging
- Initialise SQLite
- Run Remotive scraper
- Clean extracted jobs
- Generate dedup fingerprints
- Validate records
- Load jobs into SQLite
- Log pipeline run
- Print run summary

Later stages:
- Export CSV
- Generate reports
- Add more sources
"""

from __future__ import annotations

import logging
import logging.handlers
import pprint
import sys
import time
from pathlib import Path

from etl.extract.base_scraper import ScraperConfig
from etl.extract.remotive import RemotiveScraper
from etl.load.db import check_db_ready, close_connection, get_connection, init_db
from etl.load.loader import load_jobs, log_pipeline_run
from etl.transform.cleaner import clean_job_record
from etl.transform.deduper import add_fingerprints
from etl.transform.validator import validate_jobs


_LOG_DIR = Path("logs")
_LOG_FILE = _LOG_DIR / "pipeline.log"
_LOG_MAX_BYTES = 5 * 1024 * 1024
_LOG_BACKUP_COUNT = 3

_FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_CONSOLE_FORMAT = "%(levelname)-8s | %(message)s"

logger = logging.getLogger(__name__)


class _MaxLevelFilter(logging.Filter):
    """
    Pass only records at or below max_level.

    Used so INFO logs go to stdout, while WARNING+ goes to stderr.
    """

    def __init__(self, max_level: int) -> None:
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.max_level


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure rotating file logging and console logging.
    """
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    if root.handlers:
        return

    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT))

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.addFilter(_MaxLevelFilter(logging.INFO))
    stdout_handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT))

    root.addHandler(file_handler)
    root.addHandler(stdout_handler)
    root.addHandler(stderr_handler)


def main() -> None:
    setup_logging()
    logger.info("Pipeline started")

    start_time = time.perf_counter()
    conn = None

    scraper_config = ScraperConfig(
        delay_seconds=1.0,
        max_retries=3,
        backoff_factor=2.0,
        timeout_seconds=20.0,
    )

    try:
        conn = get_connection("jobs.db")
        init_db(conn)

        if not check_db_ready(conn):
            raise RuntimeError("Database setup failed: required tables missing")

        logger.info("Database initialised successfully")

        with RemotiveScraper(
            base_url="https://remotive.com/api/remote-jobs",
            config=scraper_config,
        ) as scraper:
            raw_jobs = scraper.scrape(
                keyword="data analyst",
                location="remote",
                max_pages=1,
            )

        cleaned_jobs = [clean_job_record(job) for job in raw_jobs]
        fingerprinted_jobs = add_fingerprints(cleaned_jobs)
        validated_jobs = validate_jobs(fingerprinted_jobs)

        active_count = sum(1 for job in validated_jobs if job["status"] == "active")
        incomplete_count = sum(
            1 for job in validated_jobs if job["status"] == "incomplete"
        )

        load_stats = load_jobs(conn, validated_jobs)

        duration_secs = time.perf_counter() - start_time

        log_pipeline_run(
            conn=conn,
            source="remotive",
            rows_extracted=len(raw_jobs),
            rows_loaded=load_stats["rows_loaded"],
            rows_skipped=load_stats["rows_skipped"],
            rows_failed=load_stats["rows_failed"],
            duration_secs=duration_secs,
        )

        logger.info("Raw jobs extracted: %d", len(raw_jobs))
        logger.info("Cleaned jobs generated: %d", len(cleaned_jobs))
        logger.info(
            "Validated jobs: active=%d incomplete=%d",
            active_count,
            incomplete_count,
        )
        logger.info(
            "Load stats: loaded=%d skipped=%d failed=%d duration=%.2fs",
            load_stats["rows_loaded"],
            load_stats["rows_skipped"],
            load_stats["rows_failed"],
            duration_secs,
        )

        print("Pipeline run completed")
        print(f"Extracted: {len(raw_jobs)}")
        print(f"Cleaned: {len(cleaned_jobs)}")
        print(f"Active: {active_count}")
        print(f"Incomplete: {incomplete_count}")
        print(f"Loaded: {load_stats['rows_loaded']}")
        print(f"Skipped duplicates: {load_stats['rows_skipped']}")
        print(f"Failed: {load_stats['rows_failed']}")
        print(f"Duration seconds: {duration_secs:.2f}")
        print()
        print("Sample validated record:")

        if validated_jobs:
            pprint.pp(validated_jobs[0], sort_dicts=False)
        else:
            print("No jobs found")

        logger.info("Pipeline finished successfully")

    except Exception:
        logger.exception("Pipeline failed with an unhandled exception")
        sys.exit(1)

    finally:
        close_connection(conn)


if __name__ == "__main__":
    main()