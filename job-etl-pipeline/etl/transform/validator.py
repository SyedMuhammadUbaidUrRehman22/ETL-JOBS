"""
validator.py — Required-field validation for cleaned job records.

The validator marks records as:
    active      → required fields are present
    incomplete  → title, company, or URL is missing

Duplicate handling will happen later in the load layer when comparing
fingerprints against SQLite.
"""

from __future__ import annotations

from typing import Any


REQUIRED_FIELDS = ["title", "company", "url"]


def get_missing_required_fields(job: dict[str, Any]) -> list[str]:
    """
    Return required fields that are missing or blank.
    """
    missing_fields: list[str] = []

    for field in REQUIRED_FIELDS:
        value = job.get(field)

        if value is None:
            missing_fields.append(field)
            continue

        if isinstance(value, str) and not value.strip():
            missing_fields.append(field)

    return missing_fields


def validate_job(job: dict[str, Any]) -> dict[str, Any]:
    """
    Validate one cleaned job record.

    Adds:
        status
        missing_fields
    """
    validated_job = job.copy()
    missing_fields = get_missing_required_fields(validated_job)

    if missing_fields:
        validated_job["status"] = "incomplete"
    else:
        validated_job["status"] = "active"

    validated_job["missing_fields"] = missing_fields

    return validated_job


def validate_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Validate a list of cleaned job records.
    """
    return [validate_job(job) for job in jobs]