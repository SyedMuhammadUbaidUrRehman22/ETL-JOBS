"""
main.py — Pipeline entry point.

Current stage:
- Load config.yaml
- Apply CLI overrides
- Setup logging
- Initialise SQLite
- Run enabled source scrapers
- Clean extracted jobs
- Generate dedup fingerprints
- Validate records
- Load jobs into SQLite
- Log pipeline run
- Export clean jobs to CSV
- Generate CSV and HTML reports
- Print run summary
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import pprint
import sys
import time
from pathlib import Path
from typing import Any

from etl.config import get_enabled_sources, load_config
from etl.extract.base_scraper import ScraperConfig
from etl.extract.remotive import RemotiveScraper
from etl.load.db import check_db_ready, close_connection, get_connection, init_db
from etl.load.exporter import export_jobs_to_csv
from etl.load.loader import load_jobs, log_pipeline_run
from etl.transform.cleaner import clean_job_record
from etl.transform.deduper import add_fingerprints
from etl.transform.validator import validate_jobs
from reports.generator import generate_reports


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


def setup_logging(
    level: int = logging.INFO,
    log_file: str = "logs/pipeline.log",
) -> None:
    """
    Configure rotating file logging and console logging.
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    if root.handlers:
        return

    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
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


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Automated Job Market ETL Pipeline"
    )

    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML config file. Default: config.yaml",
    )

    parser.add_argument(
        "--keyword",
        default=None,
        help="Override keyword from config.yaml",
    )

    parser.add_argument(
        "--location",
        default=None,
        help="Override location from config.yaml",
    )

    parser.add_argument(
        "--source",
        default=None,
        help="Run only one source, e.g. remotive",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Override max_pages from config.yaml",
    )

    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Generate reports from existing SQLite data without scraping",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG logging",
    )

    return parser.parse_args()


def apply_cli_overrides(
    config: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    """
    Apply CLI overrides to loaded config.
    """
    if args.keyword is not None:
        config["filters"]["keyword"] = args.keyword

    if args.location is not None:
        config["filters"]["location"] = args.location

    if args.max_pages is not None:
        config["scraping"]["max_pages"] = args.max_pages

    if args.source is not None:
        requested_source = args.source.strip().lower()

        if requested_source not in config["sources"]:
            available_sources = ", ".join(config["sources"].keys())
            raise ValueError(
                f"Unknown source: {requested_source}. "
                f"Available sources: {available_sources}"
            )

        for source_name in config["sources"]:
            config["sources"][source_name]["enabled"] = source_name == requested_source

    return config


def build_scraper_config(config: dict[str, Any]) -> ScraperConfig:
    """
    Build ScraperConfig from config.yaml scraping section.
    """
    scraping_config = config["scraping"]

    return ScraperConfig(
        delay_seconds=float(scraping_config.get("delay_seconds", 1.0)),
        max_retries=int(scraping_config.get("max_retries", 3)),
        backoff_factor=float(scraping_config.get("backoff_factor", 2.0)),
        timeout_seconds=float(scraping_config.get("timeout_seconds", 20.0)),
    )


def run_remotive_source(
    source_config: dict[str, Any],
    scraper_config: ScraperConfig,
    keyword: str | None,
    location: str | None,
    max_pages: int,
) -> list[dict[str, Any]]:
    """
    Run Remotive scraper and return raw jobs.
    """
    with RemotiveScraper(
        base_url=source_config["base_url"],
        config=scraper_config,
    ) as scraper:
        return scraper.scrape(
            keyword=keyword,
            location=location,
            max_pages=max_pages,
        )


def main() -> None:
    args = parse_args()

    config = load_config(args.config)
    config = apply_cli_overrides(config, args)

    log_level = logging.DEBUG if args.debug else logging.INFO

    setup_logging(
        level=log_level,
        log_file=config.get("logging", {}).get("log_file", "logs/pipeline.log"),
    )

    logger.info("Pipeline started")

    start_time = time.perf_counter()
    conn = None

    scraper_config = build_scraper_config(config)

    db_path = config["database"]["path"]
    clean_csv_path = config["output"]["clean_csv"]
    report_dir = config["output"]["report_dir"]

    keyword = config["filters"].get("keyword")
    location = config["filters"].get("location")
    max_pages = int(config["scraping"].get("max_pages", 1))

    enabled_sources = get_enabled_sources(config)

    try:
        conn = get_connection(db_path)
        init_db(conn)

        if not check_db_ready(conn):
            raise RuntimeError("Database setup failed: required tables missing")

        logger.info("Database initialised successfully")

        if args.report_only:
            report_result = generate_reports(
                conn=conn,
                output_dir=report_dir,
            )

            exported_rows = export_jobs_to_csv(
                conn=conn,
                output_path=clean_csv_path,
            )

            print("Report-only run completed")
            print(f"Exported CSV rows: {exported_rows}")
            print(f"Report CSV: {report_result['csv_path']}")
            print(f"Report HTML: {report_result['html_path']}")

            logger.info(
                "Report-only run completed jobs_count=%d csv=%s html=%s",
                report_result["jobs_count"],
                report_result["csv_path"],
                report_result["html_path"],
            )

            return

        all_raw_jobs: list[dict[str, Any]] = []

        for source_name, source_config in enabled_sources.items():
            logger.info("Running source=%s", source_name)

            if source_name == "remotive":
                source_jobs = run_remotive_source(
                    source_config=source_config,
                    scraper_config=scraper_config,
                    keyword=keyword,
                    location=location,
                    max_pages=max_pages,
                )
            else:
                logger.warning(
                    "Source enabled but scraper not implemented yet: %s",
                    source_name,
                )
                source_jobs = []

            logger.info(
                "Source completed source=%s rows_extracted=%d",
                source_name,
                len(source_jobs),
            )

            all_raw_jobs.extend(source_jobs)

        cleaned_jobs = [clean_job_record(job) for job in all_raw_jobs]
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
            source=",".join(enabled_sources.keys()),
            rows_extracted=len(all_raw_jobs),
            rows_loaded=load_stats["rows_loaded"],
            rows_skipped=load_stats["rows_skipped"],
            rows_failed=load_stats["rows_failed"],
            duration_secs=duration_secs,
        )

        exported_rows = export_jobs_to_csv(
            conn=conn,
            output_path=clean_csv_path,
        )

        report_result = generate_reports(
            conn=conn,
            output_dir=report_dir,
        )

        logger.info("Raw jobs extracted: %d", len(all_raw_jobs))
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
        logger.info("CSV export completed rows=%d", exported_rows)
        logger.info(
            "Reports generated jobs_count=%d csv=%s html=%s",
            report_result["jobs_count"],
            report_result["csv_path"],
            report_result["html_path"],
        )

        print("Pipeline run completed")
        print(f"Enabled sources: {', '.join(enabled_sources.keys())}")
        print(f"Keyword: {keyword}")
        print(f"Location: {location}")
        print(f"Extracted: {len(all_raw_jobs)}")
        print(f"Cleaned: {len(cleaned_jobs)}")
        print(f"Active: {active_count}")
        print(f"Incomplete: {incomplete_count}")
        print(f"Loaded: {load_stats['rows_loaded']}")
        print(f"Skipped duplicates: {load_stats['rows_skipped']}")
        print(f"Failed: {load_stats['rows_failed']}")
        print(f"Exported CSV rows: {exported_rows}")
        print(f"Report CSV: {report_result['csv_path']}")
        print(f"Report HTML: {report_result['html_path']}")
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