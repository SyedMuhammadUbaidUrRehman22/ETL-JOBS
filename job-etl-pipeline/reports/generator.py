"""
generator.py — Pandas-based report generation.

Responsibilities:
- Read clean job data from SQLite
- Generate summary analytics
- Export report CSV
- Export report HTML
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


logger = logging.getLogger(__name__)


# =========================
# DATA LOADING
# =========================

def load_jobs_dataframe(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Load active and incomplete jobs from SQLite into a DataFrame.
    """
    query = """
        SELECT
            id,
            fingerprint,
            title,
            seniority_level,
            company,
            city,
            region,
            remote_flag,
            salary_min,
            salary_max,
            salary_currency,
            date_posted,
            source,
            url,
            description,
            status,
            first_seen,
            last_seen
        FROM jobs
        WHERE status IN ('active', 'incomplete');
    """

    df = pd.read_sql_query(query, conn)

    if not df.empty:
        df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")
        df["first_seen"] = pd.to_datetime(df["first_seen"], errors="coerce")
        df["last_seen"] = pd.to_datetime(df["last_seen"], errors="coerce")

    return df


# =========================
# ANALYTICS HELPERS
# =========================

def top_titles(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    """
    Top job titles by frequency.
    """
    if df.empty or "title" not in df.columns:
        return pd.DataFrame(columns=["title", "count"])

    return (
        df["title"]
        .fillna("Unknown")
        .value_counts()
        .head(limit)
        .rename_axis("title")
        .reset_index(name="count")
    )


def top_companies(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    """
    Top hiring companies by frequency.
    """
    if df.empty or "company" not in df.columns:
        return pd.DataFrame(columns=["company", "count"])

    return (
        df["company"]
        .fillna("Unknown")
        .value_counts()
        .head(limit)
        .rename_axis("company")
        .reset_index(name="count")
    )


def salary_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Salary distribution summary by title.
    """
    if df.empty:
        return pd.DataFrame(columns=[
            "title",
            "salary_currency",
            "count",
            "salary_min",
            "salary_median",
            "salary_max",
        ])

    salary_df = df.dropna(subset=["salary_min", "salary_max"]).copy()

    if salary_df.empty:
        return pd.DataFrame(columns=[
            "title",
            "salary_currency",
            "count",
            "salary_min",
            "salary_median",
            "salary_max",
        ])

    salary_df["salary_midpoint"] = (
        salary_df["salary_min"].astype(float)
        + salary_df["salary_max"].astype(float)
    ) / 2

    return (
        salary_df.groupby(["title", "salary_currency"], dropna=False)
        .agg(
            count=("id", "count"),
            salary_min=("salary_min", "min"),
            salary_median=("salary_midpoint", "median"),
            salary_max=("salary_max", "max"),
        )
        .reset_index()
        .sort_values(["count", "salary_median"], ascending=[False, False])
    )


def remote_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remote vs on-site breakdown.
    """
    if df.empty or "remote_flag" not in df.columns:
        return pd.DataFrame(columns=["work_mode", "count"])

    work_mode = df["remote_flag"].map({
        1: "remote",
        True: "remote",
        0: "on_site_or_unspecified",
        False: "on_site_or_unspecified",
    })

    return (
        work_mode
        .fillna("on_site_or_unspecified")
        .value_counts()
        .rename_axis("work_mode")
        .reset_index(name="count")
    )


def new_postings_last_30_days(df: pd.DataFrame) -> pd.DataFrame:
    """
    New postings per day for the last 30 days.
    """
    if df.empty or "first_seen" not in df.columns:
        return pd.DataFrame(columns=["date", "new_postings"])

    recent_df = df.dropna(subset=["first_seen"]).copy()

    if recent_df.empty:
        return pd.DataFrame(columns=["date", "new_postings"])

    max_date = recent_df["first_seen"].max().normalize()
    min_date = max_date - pd.Timedelta(days=29)

    recent_df = recent_df[
        (recent_df["first_seen"] >= min_date)
        & (recent_df["first_seen"] <= max_date)
    ].copy()

    recent_df["date"] = recent_df["first_seen"].dt.date

    return (
        recent_df.groupby("date")
        .size()
        .reset_index(name="new_postings")
        .sort_values("date")
    )


# =========================
# REPORT BUILDING
# =========================

def build_report_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Build all report tables.
    """
    return {
        "top_titles": top_titles(df),
        "top_companies": top_companies(df),
        "salary_summary": salary_summary(df),
        "remote_breakdown": remote_breakdown(df),
        "new_postings_last_30_days": new_postings_last_30_days(df),
    }


# =========================
# EXPORT: CSV
# =========================

def export_report_csv(
    report_tables: dict[str, pd.DataFrame],
    output_dir: str = "output",
) -> Path:
    """
    Export report tables into a single CSV file.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    report_path = output_path / f"report_{today}.csv"

    frames: list[pd.DataFrame] = []

    for section_name, table in report_tables.items():
        table_copy = table.copy()
        table_copy.insert(0, "report_section", section_name)
        frames.append(table_copy)

    combined = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()

    combined.to_csv(report_path, index=False, encoding="utf-8")

    logger.info("Exported report CSV path=%s rows=%d", report_path, len(combined))

    return report_path


# =========================
# EXPORT: HTML
# =========================

def export_report_html(
    report_tables: dict[str, pd.DataFrame],
    output_dir: str = "output",
) -> Path:
    """
    Export report tables into an HTML file.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    report_path = output_path / f"report_{today}.html"

    sections: list[str] = []

    for section_name, table in report_tables.items():
        pretty_title = section_name.replace("_", " ").title()

        html_table = (
            "<p>No data available.</p>"
            if table.empty
            else table.to_html(index=False, escape=True)
        )

        sections.append(f"""
        <section>
            <h2>{pretty_title}</h2>
            {html_table}
        </section>
        """)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Job Market ETL Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                color: #222;
            }}
            h1 {{
                margin-bottom: 4px;
            }}
            .subtitle {{
                color: #666;
                margin-bottom: 30px;
            }}
            section {{
                margin-bottom: 36px;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin-top: 10px;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }}
            th {{
                background: #f4f4f4;
            }}
            tr:nth-child(even) {{
                background: #fafafa;
            }}
        </style>
    </head>
    <body>
        <h1>Job Market ETL Report</h1>
        <p class="subtitle">Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        {''.join(sections)}
    </body>
    </html>
    """

    report_path.write_text(html, encoding="utf-8")

    logger.info("Exported report HTML path=%s", report_path)

    return report_path


# =========================
# MAIN ENTRY
# =========================

def generate_reports(
    conn: sqlite3.Connection,
    output_dir: str = "output",
) -> dict[str, Any]:
    """
    Generate all report outputs.
    """
    df = load_jobs_dataframe(conn)
    report_tables = build_report_tables(df)

    csv_path = export_report_csv(report_tables, output_dir=output_dir)
    html_path = export_report_html(report_tables, output_dir=output_dir)

    return {
        "jobs_count": len(df),
        "csv_path": str(csv_path),
        "html_path": str(html_path),
    }