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

from etl.extract.hn_hiring import HNHiringScraper
from etl.extract.remoteok import RemoteOKScraper
from etl.extract.weworkremotely import WeWorkRemotelyScraper
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
    def __init__(self, max_level: int) -> None:
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.max_level


def setup_logging(
    level: int = logging.INFO,
    log_file: str = "logs/pipeline.log",
) -> None:
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
    parser = argparse.ArgumentParser(
        description="Automated Job Market ETL Pipeline"
    )

    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--keyword", default=None)
    parser.add_argument("--location", default=None)
    parser.add_argument("--source", default=None)
    parser.add_argument("--max-pages", type=int, default=None)

    parser.add_argument(
        "--report-only",
        action="store_true",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
    )

    return parser.parse_args()


def apply_cli_overrides(
    config: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:

    if args.keyword is not None:
        config["filters"]["keyword"] = args.keyword

    if args.location is not None:
        config["filters"]["location"] = args.location

    if args.max_pages is not None:
        config["scraping"]["max_pages"] = args.max_pages

    if args.source is not None:
        requested_source = args.source.strip().lower()

        if requested_source not in config["sources"]:
            raise ValueError(
                f"Unknown source: {requested_source}. "
                f"Available: {', '.join(config['sources'].keys())}"
            )

        for source_name in config["sources"]:
            config["sources"][source_name]["enabled"] = (
                source_name == requested_source
            )

    return config


def build_scraper_config(config: dict[str, Any]) -> ScraperConfig:
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
    with RemotiveScraper(
        base_url=source_config["base_url"],
        config=scraper_config,
    ) as scraper:
        return scraper.scrape(
            keyword=keyword,
            location=location,
            max_pages=max_pages,
        )
def run_remoteok_source(
    source_config: dict[str, Any],
    scraper_config: ScraperConfig,
    keyword: str | None,
    location: str | None,
    max_pages: int,
) -> list[dict[str, Any]]:
    """
    Run RemoteOK scraper and return filtered raw jobs.
    """
    with RemoteOKScraper(
        base_url=source_config["base_url"],
        config=scraper_config,
    ) as scraper:
        jobs = scraper.scrape(
            keyword=keyword,
            location=location,
            max_pages=max_pages,
        )

    return filter_raw_jobs(jobs, keyword=keyword, location=location)


def run_weworkremotely_source(
    source_config: dict[str, Any],
    scraper_config: ScraperConfig,
    keyword: str | None,
    location: str | None,
    max_pages: int,
) -> list[dict[str, Any]]:
    """
    Run We Work Remotely scraper and return filtered raw jobs.
    """
    with WeWorkRemotelyScraper(
        base_url=source_config["base_url"],
        config=scraper_config,
    ) as scraper:
        jobs = scraper.scrape(
            keyword=keyword,
            location=location,
            max_pages=max_pages,
        )

    return filter_raw_jobs(jobs, keyword=keyword, location=location)


def run_hn_hiring_source(
    source_config: dict[str, Any],
    scraper_config: ScraperConfig,
    keyword: str | None,
    location: str | None,
    max_pages: int,
) -> list[dict[str, Any]]:
    """
    Run HN Who's Hiring scraper and return raw jobs.
    """
    with HNHiringScraper(
        base_url=source_config["base_url"],
        config=scraper_config,
    ) as scraper:
        return scraper.scrape(
            keyword=keyword,
            location=location,
            max_pages=max_pages,
        )


def filter_raw_jobs(
    jobs: list[dict[str, Any]],
    keyword: str | None,
    location: str | None,
) -> list[dict[str, Any]]:
    """
    Apply simple raw keyword/location filtering to source outputs.
    """
    filtered = jobs

    if keyword:
        keyword_lower = keyword.lower()
        filtered = [
            job
            for job in filtered
            if keyword_lower
            in (
                f"{job.get('title', '')} "
                f"{job.get('company', '')} "
                f"{job.get('description', '')}"
            ).lower()
        ]

    if location:
        location_lower = location.lower()

        if location_lower != "remote":
            filtered = [
                job
                for job in filtered
                if location_lower in str(job.get("location", "")).lower()
            ]

    return filtered

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
            raise RuntimeError("Database setup failed")

        logger.info("Database initialised successfully")

        if args.report_only:
            report_result = generate_reports(conn=conn, output_dir=report_dir)

            exported_rows = export_jobs_to_csv(
                conn=conn,
                output_path=clean_csv_path,
            )

            print("Report-only run completed")
            print(f"Exported CSV rows: {exported_rows}")
            print(f"Report CSV: {report_result['csv_path']}")
            print(f"Report HTML: {report_result['html_path']}")
            return

        all_raw_jobs: list[dict[str, Any]] = []

        for source_name, source_config in enabled_sources.items():
            logger.info("Running source=%s", source_name)

            if source_name == "remotive":
                source_jobs = run_remotive_source(
                    source_config,
                    scraper_config,
                    keyword,
                    location,
                    max_pages,
                )

            elif source_name == "remoteok":
                source_jobs = run_remoteok_source(
                    source_config,
                    scraper_config,
                    keyword,
                    location,
                    max_pages,
                )

            elif source_name == "weworkremotely":
                source_jobs = run_weworkremotely_source(
                    source_config,
                    scraper_config,
                    keyword,
                    location,
                    max_pages,
                )

            elif source_name == "hn_hiring":
                source_jobs = run_hn_hiring_source(
                    source_config,
                    scraper_config,
                    keyword,
                    location,
                    max_pages,
                )

            else:
                logger.warning("Unknown enabled source: %s", source_name)
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

        active_count = sum(j["status"] == "active" for j in validated_jobs)
        incomplete_count = sum(j["status"] == "incomplete" for j in validated_jobs)

        load_stats = load_jobs(conn, validated_jobs)

        duration_secs = time.perf_counter() - start_time

        log_pipeline_run(
            conn,
            ",".join(enabled_sources.keys()),
            len(all_raw_jobs),
            load_stats["rows_loaded"],
            load_stats["rows_skipped"],
            load_stats["rows_failed"],
            duration_secs,
        )

        exported_rows = export_jobs_to_csv(conn, clean_csv_path)
        report_result = generate_reports(conn, report_dir)

        logger.info("Pipeline finished successfully")

    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)

    finally:
        close_connection(conn)


if __name__ == "__main__":
    main()