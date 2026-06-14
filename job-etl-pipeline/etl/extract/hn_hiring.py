"""
hn_hiring.py — Hacker News Who's Hiring scraper.

This source is intentionally semi-structured:
- Finds recent "Who is hiring?" discussions through Algolia-style search
- Pulls comments from the story
- Treats each top-level comment as a raw job posting candidate

HN comments are messy by nature, which is useful for demonstrating text cleaning.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any, Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from etl.extract.base_scraper import BaseScraper, ScraperConfig, ScraperError


logger = logging.getLogger(__name__)


ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items/{object_id}"


class HNHiringScraper(BaseScraper):
    """
    Scraper for HN Who's Hiring monthly threads.
    """

    def __init__(
        self,
        base_url: str,
        config: Optional[ScraperConfig] = None,
    ) -> None:
        super().__init__(
            source_name="hn_hiring",
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
        Build Algolia search URL for recent HN Who's Hiring threads.
        """
        _ = keyword
        _ = location

        params = {
            "query": "Ask HN: Who is hiring?",
            "tags": "story",
            "page": max(page - 1, 0),
            "hitsPerPage": 5,
        }

        return f"{self.base_url}?{urlencode(params)}"

    def parse(self, raw_response: str) -> list[dict[str, Any]]:
        """
        Parse search response, then fetch the most relevant story comments.
        """
        search_data = requests.models.complexjson.loads(raw_response)
        hits = search_data.get("hits", [])

        story = self._select_who_is_hiring_story(hits)

        if not story:
            logger.warning("No HN Who's Hiring story found")
            return []

        object_id = story.get("objectID")

        if not object_id:
            logger.warning("HN story missing objectID")
            return []

        item_url = ALGOLIA_ITEM_URL.format(object_id=object_id)

        try:
            item_raw = self.fetch(item_url)
            item_data = requests.models.complexjson.loads(item_raw)
        except Exception as exc:
            raise ScraperError(f"Failed to fetch HN item thread: {item_url}") from exc

        comments = item_data.get("children", [])

        parsed_jobs: list[dict[str, Any]] = []

        for comment in comments:
            job = self._parse_comment(comment)
            if job:
                parsed_jobs.append(job)

        return parsed_jobs

    def scrape(
        self,
        keyword: Optional[str] = None,
        location: Optional[str] = None,
        max_pages: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Override scrape so keyword/location filtering can happen after parsing
        because HN comments are free text.
        """
        jobs = super().scrape(
            keyword=keyword,
            location=location,
            max_pages=max_pages,
        )

        return self._filter_jobs(jobs, keyword=keyword, location=location)

    @staticmethod
    def _select_who_is_hiring_story(hits: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """
        Select the most recent likely Who's Hiring story.
        """
        for hit in hits:
            title = (hit.get("title") or "").lower()

            if "who is hiring" in title or "who's hiring" in title:
                return hit

        return hits[0] if hits else None

    def _parse_comment(self, comment: dict[str, Any]) -> Optional[dict[str, Any]]:
        """
        Convert one HN comment into a raw job dictionary.
        """
        text_html = comment.get("text")

        if not text_html:
            return None

        text = self._clean_hn_html(text_html)

        if not text or len(text) < 30:
            return None

        company, title, location = self._infer_fields_from_comment(text)
        url = self._extract_first_url(text_html)

        return {
            "title": title,
            "company": company,
            "location": location,
            "salary": self._extract_salary_text(text),
            "date_posted": comment.get("created_at"),
            "url": url,
            "source": "hn_hiring",
            "description": text,
        }

    @staticmethod
    def _clean_hn_html(text_html: str) -> str:
        """
        Clean HN comment HTML into plain text.
        """
        unescaped = html.unescape(text_html)
        soup = BeautifulSoup(unescaped, "html.parser")
        text = soup.get_text(separator=" ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _extract_first_url(text_html: str) -> Optional[str]:
        """
        Extract first link from a HN comment if present.
        """
        soup = BeautifulSoup(text_html, "html.parser")
        link = soup.find("a")

        if not link:
            return None

        href = link.get("href")

        if not href:
            return None

        return str(href)

    @staticmethod
    def _infer_fields_from_comment(text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Infer company/title/location from HN free text.

        HN comments often start like:
            Company | Role | Location | Remote
        """
        first_part = text.split(".", 1)[0]
        separators = r"\s+\|\s+|\s+-\s+| — "

        parts = [p.strip() for p in re.split(separators, first_part) if p.strip()]

        company = parts[0] if len(parts) >= 1 else None
        title = parts[1] if len(parts) >= 2 else "Software / Data Role"

        location_candidates = [
            part for part in parts[2:]
            if any(
                token in part.lower()
                for token in ["remote", "onsite", "hybrid", "usa", "canada", "europe", "uk"]
            )
        ]

        location = location_candidates[0] if location_candidates else "Unknown"

        return company, title, location

    @staticmethod
    def _extract_salary_text(text: str) -> Optional[str]:
        """
        Extract a salary-like substring from HN comment text.
        """
        salary_pattern = re.compile(
            r"([$£€]\s?\d[\d,]*(?:k|K)?(?:\s?[-–]\s?[$£€]?\s?\d[\d,]*(?:k|K)?)?)"
        )

        match = salary_pattern.search(text)

        if match:
            return match.group(1)

        return None

    @staticmethod
    def _filter_jobs(
        jobs: list[dict[str, Any]],
        keyword: Optional[str],
        location: Optional[str],
    ) -> list[dict[str, Any]]:
        """
        Apply simple keyword/location filtering to HN comments.
        """
        filtered = jobs

        if keyword:
            keyword_lower = keyword.lower()
            filtered = [
                job for job in filtered
                if keyword_lower in (
                    f"{job.get('title', '')} {job.get('description', '')}"
                ).lower()
            ]

        if location:
            location_lower = location.lower()

            if location_lower != "remote":
                filtered = [
                    job for job in filtered
                    if location_lower in str(job.get("location", "")).lower()
                ]

        return filtered