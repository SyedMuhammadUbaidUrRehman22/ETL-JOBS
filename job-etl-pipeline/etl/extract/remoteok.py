"""
remoteok.py — RemoteOK JSON scraper.

RemoteOK is handled as a JSON-style source rather than fragile HTML parsing.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from urllib.parse import urlencode

from etl.extract.base_scraper import BaseScraper, ScraperConfig


logger = logging.getLogger(__name__)


class RemoteOKScraper(BaseScraper):
    """
    Scraper for RemoteOK job listings.
    """

    def __init__(
        self,
        base_url: str,
        config: Optional[ScraperConfig] = None,
    ) -> None:
        super().__init__(
            source_name="remoteok",
            base_url=base_url,
            config=config,
        )

    def build_url(
        self,
        keyword: Optional[str] = None,
        location: Optional[str] = None,
        page: int = 1,
    ) -> str:
        """
        Build RemoteOK URL.

        RemoteOK commonly exposes a JSON endpoint at /api.
        For v1, we fetch the API and filter keyword/location locally because
        the response format is more stable than HTML selectors.
        """
        _ = keyword
        _ = location
        _ = page

        return self.base_url

    def parse(self, raw_response: str) -> list[dict[str, Any]]:
        """
        Parse RemoteOK JSON response into raw job dictionaries.
        """
        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError:
            logger.exception("Failed to decode RemoteOK JSON response")
            raise

        if not isinstance(data, list):
            logger.warning("Unexpected RemoteOK response type: %s", type(data))
            return []

        parsed_jobs: list[dict[str, Any]] = []

        for item in data:
            if not isinstance(item, dict):
                continue

            # RemoteOK response may include metadata/header objects.
            if not item.get("position") and not item.get("title"):
                continue

            title = item.get("position") or item.get("title")
            company = item.get("company")
            location = item.get("location")
            salary = self._build_salary_text(item)

            url = (
                item.get("url")
                or item.get("apply_url")
                or item.get("slug")
                or item.get("id")
            )

            if url and isinstance(url, str) and url.startswith("/"):
                url = f"https://remoteok.com{url}"

            if url and isinstance(url, int):
                url = f"https://remoteok.com/remote-jobs/{url}"

            parsed_jobs.append(
                {
                    "title": title,
                    "company": company,
                    "location": location or "Remote",
                    "salary": salary,
                    "date_posted": item.get("date") or item.get("epoch"),
                    "url": url,
                    "source": "remoteok",
                    "description": item.get("description") or item.get("tags"),
                }
            )

        return parsed_jobs

    @staticmethod
    def _build_salary_text(item: dict[str, Any]) -> Optional[str]:
        """
        Build a salary string from RemoteOK salary fields when available.
        """
        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")

        if salary_min and salary_max:
            return f"${salary_min}-${salary_max}"

        if salary_min:
            return f"${salary_min}"

        if salary_max:
            return f"${salary_max}"

        return None