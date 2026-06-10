"""
deduper.py — Fingerprint generation for job deduplication.

The fingerprint is used to detect duplicate jobs across different sources.

PRD logic:
    SHA-256 hash of:
        normalised_title + company + location
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional


def _normalise_for_hash(value: Optional[str]) -> str:
    """
    Normalise text before hashing.

    This reduces false negatives caused by:
    - Case differences
    - Extra spaces
    - Punctuation differences
    """
    if value is None:
        return ""

    value = str(value).lower().strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^a-z0-9\s]", "", value)

    return value


def build_fingerprint(job: dict[str, Any]) -> str:
    """
    Build SHA-256 fingerprint for a cleaned job record.

    Uses:
        title + company + city + region

    If city is missing but region exists, region still contributes.
    This works well for remote roles where city is usually None.
    """
    title = _normalise_for_hash(job.get("title"))
    company = _normalise_for_hash(job.get("company"))
    city = _normalise_for_hash(job.get("city"))
    region = _normalise_for_hash(job.get("region"))

    fingerprint_base = "|".join([title, company, city, region])

    return hashlib.sha256(fingerprint_base.encode("utf-8")).hexdigest()


def add_fingerprint(job: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of the job with a fingerprint added.
    """
    job_with_fingerprint = job.copy()
    job_with_fingerprint["fingerprint"] = build_fingerprint(job_with_fingerprint)

    return job_with_fingerprint


def add_fingerprints(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Add fingerprints to a list of cleaned job records.
    """
    return [add_fingerprint(job) for job in jobs]