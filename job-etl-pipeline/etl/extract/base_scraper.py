"""
base_scraper.py — Foundation for all job-source scrapers.

This module provides:
- Shared scraper configuration
- HTTP session management
- Retry and backoff handling
- Request delay handling
- Common pagination orchestration
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import requests


logger = logging.getLogger(__name__)


_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; JobETLPipeline/1.0; "
    "+https://github.com/your-username/job-etl-pipeline)"
)

_RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


@dataclass
class ScraperConfig:
    """
    Shared scraper settings.

    This config can be reused across all source scrapers.
    """

    delay_seconds: float = 2.0
    max_retries: int = 3
    backoff_factor: float = 2.0
    timeout_seconds: float = 20.0
    headers: dict[str, str] = field(
        default_factory=lambda: {"User-Agent": _DEFAULT_USER_AGENT}
    )


class ScraperError(Exception):
    """Raised when a scraper cannot fetch or parse a resource."""


class BaseScraper(ABC):
    """
    Base class for all job-source scrapers.

    Subclasses must implement:
    - build_url()
    - parse()
    """

    def __init__(
        self,
        source_name: str,
        base_url: str,
        config: Optional[ScraperConfig] = None,
    ) -> None:
        self.source_name = source_name
        self.base_url = base_url
        self._config = config or ScraperConfig()
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        """
        Create a requests session with shared headers.
        """
        session = requests.Session()
        session.headers.update(self._config.headers)
        return session

    def close(self) -> None:
        """
        Close the underlying HTTP session.
        """
        self._session.close()

    def __enter__(self) -> BaseScraper:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch(self, url: str) -> str:
        """
        Retrieve URL with retry and exponential backoff.

        Retries happen for:
        - Network-level request errors
        - HTTP 429
        - HTTP 5xx transient server errors
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, self._config.max_retries + 1):
            try:
                logger.info(
                    "Fetching source=%s attempt=%d/%d url=%s",
                    self.source_name,
                    attempt,
                    self._config.max_retries,
                    url,
                )

                response = self._session.get(
                    url,
                    timeout=self._config.timeout_seconds,
                )

                if response.status_code in _RETRYABLE_STATUSES:
                    raise requests.HTTPError(
                        f"Retryable HTTP {response.status_code}",
                        response=response,
                    )

                response.raise_for_status()

                # Respectful delay after successful request.
                time.sleep(self._config.delay_seconds)

                return response.text

            except requests.RequestException as exc:
                last_error = exc
                is_final_attempt = attempt == self._config.max_retries

                if not is_final_attempt:
                    wait = self._config.backoff_factor ** attempt

                    logger.warning(
                        "Fetch failed source=%s attempt=%d error=%s retry_in=%.1fs",
                        self.source_name,
                        attempt,
                        exc,
                        wait,
                    )

                    time.sleep(wait)

        raise ScraperError(
            f"Failed to fetch {url!r} after {self._config.max_retries} attempts"
        ) from last_error

    @abstractmethod
    def build_url(
        self,
        keyword: Optional[str] = None,
        location: Optional[str] = None,
        page: int = 1,
    ) -> str:
        """
        Return the source-specific URL for the given search parameters.
        """

    @abstractmethod
    def parse(self, raw_response: str) -> list[dict]:
        """
        Parse raw response into a list of raw job dictionaries.
        """

    def scrape(
        self,
        keyword: Optional[str] = None,
        location: Optional[str] = None,
        max_pages: int = 1,
    ) -> list[dict]:
        """
        Paginate through a source and collect job listings.

        Stops early when a page returns no jobs.
        """
        all_jobs: list[dict] = []

        for page in range(1, max_pages + 1):
            url = self.build_url(
                keyword=keyword,
                location=location,
                page=page,
            )

            raw_response = self.fetch(url)
            jobs = self.parse(raw_response)

            logger.info(
                "Parsed source=%s page=%d/%d jobs=%d",
                self.source_name,
                page,
                max_pages,
                len(jobs),
            )

            if not jobs:
                logger.debug(
                    "Empty page, stopping early source=%s page=%d",
                    self.source_name,
                    page,
                )
                break

            all_jobs.extend(jobs)

        return all_jobs

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"source_name={self.source_name!r}, "
            f"base_url={self.base_url!r})"
        )