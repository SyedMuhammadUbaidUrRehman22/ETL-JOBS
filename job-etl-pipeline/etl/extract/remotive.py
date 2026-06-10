"""
remotive.py — Remotive API scraper.

Source:
    https://remotive.com/api/remote-jobs

This scraper is API-based, so it is the easiest first source to validate.
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from urllib.parse import urlencode

from etl.extract.base_scraper import BaseScraper, ScraperConfig


logger = logging.getLogger(__name__)


class RemotiveScraper(BaseScraper):
    """
    Scraper for Remotive remote job listings.
    """

    def __init__(
        self,
        base_url: str,
        config: Optional[ScraperConfig] = None,
    ) -> None:
        super().__init__(
            source_name="remotive",
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
        Build Remotive API URL.

        Remotive supports a search query parameter.
        It does not use classic page pagination, but page is accepted
        for compatibility with BaseScraper.
        """
        params: dict[str, str] = {}

        if keyword:
            params["search"] = keyword

        # Remotive jobs are remote by default, so location is intentionally
        # not sent as a query parameter for now.
        _ = location
        _ = page

        if not params:
            return self.base_url

        return f"{self.base_url}?{urlencode(params)}"

    def parse(self, raw_response: str) -> list[dict]:
        """
        Parse Remotive JSON response into standard raw job dictionaries.
        """
        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError:
            logger.exception("Failed to decode Remotive JSON response")
            raise

        jobs = data.get("jobs", [])

        parsed_jobs: list[dict] = []

        for job in jobs:
            parsed_jobs.append(
                {
                    "title": job.get("title"),
                    "company": job.get("company_name"),
                    "location": job.get("candidate_required_location"),
                    "salary": job.get("salary"),
                    "date_posted": job.get("publication_date"),
                    "url": job.get("url"),
                    "source": "remotive",
                    "description": job.get("description"),
                }
            )

        return parsed_jobs