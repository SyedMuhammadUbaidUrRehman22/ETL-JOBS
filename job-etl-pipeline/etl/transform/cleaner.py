"""
cleaner.py — Field cleaning and normalisation utilities.

This module converts raw scraped job records into cleaner, structured fields.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

from bs4 import BeautifulSoup
from dateutil import parser as date_parser


SENIORITY_PATTERNS = {
    "intern": r"\b(intern|internship|trainee)\b",
    "junior": r"\b(junior|jr\.?|entry[- ]?level|graduate)\b",
    "mid": r"\b(mid|intermediate|ii)\b",
    "senior": r"\b(senior|sr\.?|iii|iv)\b",
    "lead": r"\b(lead|principal|staff|manager|head)\b",
}


TITLE_NOISE_PATTERNS = [
    r"\bsr\.?\b",
    r"\bsenior\b",
    r"\bjr\.?\b",
    r"\bjunior\b",
    r"\blead\b",
    r"\bprincipal\b",
    r"\bstaff\b",
    r"\bmanager\b",
    r"\bhead\b",
    r"\bintern\b",
    r"\binternship\b",
    r"\btrainee\b",
    r"\bentry[- ]?level\b",
    r"\bgraduate\b",
    r"\biii\b",
    r"\bii\b",
    r"\biv\b",
]


CURRENCY_SYMBOLS = {
    "$": "USD",
    "£": "GBP",
    "€": "EUR",
    "₨": "PKR",
    "₹": "INR",
}


def strip_html(value: Optional[str]) -> Optional[str]:
    """
    Remove HTML tags and collapse excess whitespace.
    """
    if not value:
        return None

    text = BeautifulSoup(value, "html.parser").get_text(separator=" ")
    return clean_whitespace(text)


def clean_whitespace(value: Optional[str]) -> Optional[str]:
    """
    Collapse repeated spaces, tabs, and newlines.
    """
    if value is None:
        return None

    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or None


def detect_seniority(title: Optional[str]) -> Optional[str]:
    """
    Detect seniority level from job title.
    """
    if not title:
        return None

    title_lower = title.lower()

    for seniority, pattern in SENIORITY_PATTERNS.items():
        if re.search(pattern, title_lower):
            return seniority

    return None


def clean_title(title: Optional[str]) -> Optional[str]:
    """
    Remove seniority noise from title and normalise spacing.

    Example:
        "Senior Data Analyst III" -> "Data Analyst"
    """
    if not title:
        return None

    cleaned = title

    for pattern in TITLE_NOISE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"[-|,/]+", " ", cleaned)
    cleaned = clean_whitespace(cleaned)

    if not cleaned:
        return None

    return cleaned.title()


def normalise_location(location: Optional[str]) -> dict[str, Any]:
    """
    Convert raw location string into city, region, and remote flag.

    This is intentionally simple for v1. We will improve it later if needed.
    """
    if not location:
        return {
            "city": None,
            "region": None,
            "remote_flag": False,
        }

    location_clean = clean_whitespace(location)
    location_lower = location_clean.lower() if location_clean else ""

    remote_keywords = ["remote", "anywhere", "worldwide", "global"]
    remote_flag = any(word in location_lower for word in remote_keywords)

    if remote_flag:
        return {
            "city": None,
            "region": location_clean,
            "remote_flag": True,
        }

    parts = [part.strip() for part in location_clean.split(",")]

    if len(parts) >= 2:
        city = parts[0]
        region = ", ".join(parts[1:])
    else:
        city = location_clean
        region = None

    return {
        "city": city,
        "region": region,
        "remote_flag": False,
    }


def parse_salary(salary: Optional[str]) -> dict[str, Optional[int | str]]:
    """
    Parse salary text into min, max, and currency.

    Supports examples like:
        "$80k-$120k"
        "£50,000 PA"
        "€60,000 - €90,000"
        "100k"
    """
    if not salary:
        return {
            "salary_min": None,
            "salary_max": None,
            "salary_currency": None,
        }

    salary_text = clean_whitespace(salary)
    if not salary_text:
        return {
            "salary_min": None,
            "salary_max": None,
            "salary_currency": None,
        }

    currency = None

    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in salary_text:
            currency = code
            break

    if currency is None:
        upper_text = salary_text.upper()
        for code in ["USD", "GBP", "EUR", "PKR", "INR"]:
            if code in upper_text:
                currency = code
                break

    numbers = re.findall(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k)?", salary_text, re.IGNORECASE)

    parsed_numbers: list[int] = []

    for number_text, k_suffix in numbers:
        number = float(number_text.replace(",", ""))

        if k_suffix.lower() == "k":
            number *= 1000

        parsed_numbers.append(int(number))

    if not parsed_numbers:
        return {
            "salary_min": None,
            "salary_max": None,
            "salary_currency": currency,
        }

    if len(parsed_numbers) == 1:
        salary_min = parsed_numbers[0]
        salary_max = parsed_numbers[0]
    else:
        salary_min = min(parsed_numbers)
        salary_max = max(parsed_numbers)

    return {
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency,
    }


def normalise_date(value: Optional[str]) -> Optional[str]:
    """
    Convert date-like text into YYYY-MM-DD format.
    """
    if not value:
        return None

    try:
        parsed = date_parser.parse(value)
        return parsed.date().isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def clean_job_record(raw_job: dict[str, Any]) -> dict[str, Any]:
    """
    Clean one raw job dictionary into a normalised job dictionary.
    """
    raw_title = clean_whitespace(raw_job.get("title"))
    raw_description = raw_job.get("description")
    raw_location = raw_job.get("location")
    raw_salary = raw_job.get("salary")

    location_data = normalise_location(raw_location)
    salary_data = parse_salary(raw_salary)

    cleaned = {
        "title": clean_title(raw_title),
        "seniority_level": detect_seniority(raw_title),
        "company": clean_whitespace(raw_job.get("company")),
        "city": location_data["city"],
        "region": location_data["region"],
        "remote_flag": location_data["remote_flag"],
        "salary_min": salary_data["salary_min"],
        "salary_max": salary_data["salary_max"],
        "salary_currency": salary_data["salary_currency"],
        "date_posted": normalise_date(raw_job.get("date_posted")),
        "source": clean_whitespace(raw_job.get("source")),
        "url": clean_whitespace(raw_job.get("url")),
        "description": strip_html(raw_description),
        "raw_title": raw_title,
        "raw_location": clean_whitespace(raw_location),
        "raw_salary": clean_whitespace(raw_salary),
    }

    return cleaned