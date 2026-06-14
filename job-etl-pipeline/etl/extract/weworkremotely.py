"""
weworkremotely.py — We Work Remotely RSS scraper.

This uses WWR's public RSS feed instead of scraping HTML.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import quote_plus

import feedparser

from etl.extract.base_scraper import BaseScraper, ScraperConfig


logger = logging.getLogger(__name__)


class WeWorkRemotelyScraper(BaseScraper):
    """
    Scraper for We Work Remotely RSS feed.
    """

    def __init__(
        self,
        base_url: str,
        config: Optional[ScraperConfig] = None,
    ) -> None:
        super().__init__(
            source_name="weworkremotely",
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
        Build WWR RSS URL.

        WWR public RSS feed does not need pagination in v1.
        Filtering is done locally after parsing.
        """
        _ = keyword
        _ = location
        _ = page

        return self.base_url

    def parse(self, raw_response: str) -> list[dict[str, Any]]:
        """
        Parse RSS feed into raw job dictionaries.
        """
        feed = feedparser.parse(raw_response)

        if getattr(feed, "bozo", False):
            logger.warning("WWR RSS parser warning: %s", getattr(feed, "bozo_exception", ""))

        parsed_jobs: list[dict[str, Any]] = []

        for entry in feed.entries:
            title_text = entry.get("title")
            company, title = self._split_company_title(title_text)

            parsed_jobs.append(
                {
                    "title": title,
                    "company": company,
                    "location": self._extract_location(entry),
                    "salary": None,
                    "date_posted": entry.get("published") or entry.get("updated"),
                    "url": entry.get("link"),
                    "source": "weworkremotely",
                    "description": entry.get("summary") or entry.get("description"),
                }
            )

        return parsed_jobs

    @staticmethod
    def _split_company_title(title_text: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        """
        Split common WWR RSS title format.

        Examples often look like:
            "Company Name: Job Title"
        """
        if not title_text:
            return None, None

        if ":" in title_text:
            company, title = title_text.split(":", 1)
            return company.strip(), title.strip()

        return None, title_text.strip()

    @staticmethod
    def _extract_location(entry: dict[str, Any]) -> str:
        """
        Extract location/category-like information from RSS entry.
        """
        tags = entry.get("tags", [])

        tag_values = []
        for tag in tags:
            term = tag.get("term") if isinstance(tag, dict) else None
            if term:
                tag_values.append(term)

        if tag_values:
            return ", ".join(tag_values)

        return "Remote"