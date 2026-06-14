"""
streamlit_app.py — Improved Streamlit dashboard for Job Market ETL Pipeline.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "jobs.db"
CSV_FALLBACK_PATHS = [
    APP_DIR / "output" / "jobs_clean.csv",
    APP_DIR / "jobs_clean.csv",
    Path("output/jobs_clean.csv"),
    Path("jobs_clean.csv"),
]

st.set_page_config(
    page_title="JobOS — Job Market Intelligence",
    page_icon="◌",
    layout="wide",
)


# ---------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------

def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        .stApp {
            background: #F7F7F5;
        }

        .block-container {
            padding-top: 0 !important;
            padding-bottom: 3rem;
            max-width: 1440px;
        }

        #MainMenu, footer, header { visibility: hidden; }

        /* ── Hero ─────────────────────────────────────────── */
        .hero {
            background: #0F1117;
            padding: 40px 48px 44px;
            margin-bottom: 0;
            border-bottom: 1px solid #1e2130;
        }

        .hero-eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: #6EE7B7;
            margin-bottom: 20px;
        }

        .hero-dot {
            width: 6px; height: 6px;
            border-radius: 50%;
            background: #6EE7B7;
            display: inline-block;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        .hero-title {
            font-size: 44px;
            font-weight: 800;
            letter-spacing: -2px;
            line-height: 1.05;
            color: #FFFFFF;
            margin-bottom: 14px;
            max-width: 700px;
        }

        .hero-title span {
            color: #6EE7B7;
        }

        .hero-sub {
            font-size: 15px;
            line-height: 1.6;
            color: #8B8FA8;
            max-width: 560px;
            margin-bottom: 32px;
        }

        .hero-tags {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .hero-tag {
            padding: 6px 14px;
            border: 1px solid #2a2e42;
            border-radius: 2px;
            font-size: 12px;
            font-weight: 600;
            color: #8B8FA8;
            letter-spacing: 0.4px;
            background: #181C2A;
        }

        /* ── Stat bar ─────────────────────────────────────── */
        .stat-bar {
            background: #FFFFFF;
            border-bottom: 1px solid #E8E8E4;
            padding: 0 48px;
            display: flex;
            gap: 0;
        }

        .stat-item {
            padding: 20px 32px 20px 0;
            margin-right: 32px;
            border-right: 1px solid #E8E8E4;
        }

        .stat-item:last-child { border-right: none; }

        .stat-num {
            font-size: 28px;
            font-weight: 800;
            letter-spacing: -1px;
            color: #0F1117;
            line-height: 1;
            margin-bottom: 4px;
        }

        .stat-label {
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.2px;
            text-transform: uppercase;
            color: #9CA3AF;
        }

        .stat-accent { color: #059669; }

        /* ── Content area ─────────────────────────────────── */
        .content-wrap {
            padding: 28px 48px 0;
        }

        /* ── Section headers ──────────────────────────────── */
        .sec-header {
            display: flex;
            align-items: baseline;
            gap: 12px;
            margin-bottom: 16px;
        }

        .sec-title {
            font-size: 18px;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: #0F1117;
        }

        .sec-count {
            font-size: 13px;
            font-weight: 600;
            color: #9CA3AF;
        }

        /* ── KPI cards ────────────────────────────────────── */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 28px;
        }

        .kpi {
            background: #FFFFFF;
            border: 1px solid #E8E8E4;
            border-radius: 4px;
            padding: 20px 22px;
        }

        .kpi-label {
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: #9CA3AF;
            margin-bottom: 10px;
        }

        .kpi-value {
            font-size: 32px;
            font-weight: 800;
            letter-spacing: -1.5px;
            color: #0F1117;
            line-height: 1;
            margin-bottom: 6px;
        }

        .kpi-note {
            font-size: 12px;
            color: #9CA3AF;
        }

        .kpi-value.accent { color: #059669; }
        .kpi-value.warn   { color: #D97706; }
        .kpi-value.info   { color: #2563EB; }

        /* ── Chart cards ──────────────────────────────────── */
        .chart-card {
            background: #FFFFFF;
            border: 1px solid #E8E8E4;
            border-radius: 4px;
            padding: 22px 24px;
            margin-bottom: 16px;
        }

        /* ── Tabs ─────────────────────────────────────────── */
        div[data-testid="stTabs"] {
            margin-top: 4px;
        }

        button[data-baseweb="tab"] {
            background: transparent !important;
            border: none !important;
            border-bottom: 2px solid transparent !important;
            padding: 12px 18px !important;
            margin-right: 4px !important;
            border-radius: 0 !important;
            font-weight: 600 !important;
            font-size: 13px !important;
            color: #9CA3AF !important;
        }

        button[data-baseweb="tab"] p {
            color: inherit !important;
            font-weight: inherit !important;
            font-size: inherit !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            background: transparent !important;
            color: #0F1117 !important;
            border-bottom: 2px solid #059669 !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] p {
            color: #0F1117 !important;
        }

        div[role="tabpanel"] {
            padding-top: 24px;
        }

        /* ── Table ────────────────────────────────────────── */
        div[data-testid="stDataFrame"] {
            border-radius: 4px;
            overflow: hidden;
            border: 1px solid #E8E8E4;
        }

        /* ── Sidebar ──────────────────────────────────────── */
        section[data-testid="stSidebar"] {
            background: #0F1117;
            border-right: 1px solid #1e2130;
        }

        section[data-testid="stSidebar"] > div {
            padding-top: 2rem;
        }

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] span {
            color: #F9FAFB !important;
        }

        section[data-testid="stSidebar"] .stCaption {
            color: #6B7280 !important;
        }

        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] div[data-baseweb="select"] {
            background: #181C2A !important;
            border-color: #2a2e42 !important;
            color: #F9FAFB !important;
        }

        section[data-testid="stSidebar"] div[data-baseweb="select"] span {
            color: #F9FAFB !important;
        }

        /* ── Download button ──────────────────────────────── */
        .stDownloadButton button {
            background: #0F1117 !important;
            color: #FFFFFF !important;
            border-radius: 3px !important;
            border: none !important;
            padding: 10px 20px !important;
            font-weight: 700 !important;
            font-size: 13px !important;
            letter-spacing: 0.3px;
        }

        .stDownloadButton button:hover {
            background: #1e2130 !important;
        }

        /* ── Health indicator ─────────────────────────────── */
        .health-row {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 0;
            border-bottom: 1px solid #F3F4F6;
            font-size: 14px;
        }

        .health-row:last-child { border-bottom: none; }

        .health-dot {
            width: 8px; height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
        }

        .dot-green { background: #10B981; }
        .dot-amber { background: #F59E0B; }
        .dot-red   { background: #EF4444; }

        .health-field { color: #374151; font-weight: 600; }
        .health-val   { margin-left: auto; color: #6B7280; font-size: 13px; }

        hr { margin: 28px 0; border-color: #E8E8E4; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_jobs_from_sqlite(db_path: str) -> pd.DataFrame:
    query = """
        SELECT id, title, seniority_level, company, city, region, remote_flag,
               salary_min, salary_max, salary_currency, date_posted, source,
               url, description, status, first_seen, last_seen
        FROM jobs
        WHERE status IN ('active', 'incomplete')
        ORDER BY last_seen DESC, id DESC;
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn)
    return prepare_dataframe(df)


@st.cache_data(show_spinner=False)
def load_jobs_from_csv(csv_path: str) -> pd.DataFrame:
    return prepare_dataframe(pd.read_csv(csv_path))


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    for col in ["date_posted", "first_seen", "last_seen"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    if "remote_flag" in df.columns:
        df["remote_flag"] = df["remote_flag"].astype(bool)
    if "salary_min" in df.columns:
        df["salary_min"] = pd.to_numeric(df["salary_min"], errors="coerce")
    if "salary_max" in df.columns:
        df["salary_max"] = pd.to_numeric(df["salary_max"], errors="coerce")
    if "salary_min" in df.columns and "salary_max" in df.columns:
        df["salary_midpoint"] = (df["salary_min"] + df["salary_max"]) / 2
    return df


def load_data() -> pd.DataFrame:
    if DB_PATH.exists():
        return load_jobs_from_sqlite(str(DB_PATH))
    for csv_path in CSV_FALLBACK_PATHS:
        if csv_path.exists():
            return load_jobs_from_csv(str(csv_path))
    return pd.DataFrame()


# ---------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------

def render_hero(df: pd.DataFrame) -> None:
    source_count = df["source"].nunique() if "source" in df.columns else 0
    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-eyebrow">
                <span class="hero-dot"></span>
                Live Pipeline
            </div>
            <div class="hero-title">Job Market<br><span>Intelligence</span></div>
            <div class="hero-sub">
                Full ETL workflow: scraping, cleaning, deduplication, SQLite storage,
                and analytics — built as a portfolio-grade data engineering project.
            </div>
            <div class="hero-tags">
                <span class="hero-tag">SQLite</span>
                <span class="hero-tag">Pandas</span>
                <span class="hero-tag">Deduplication</span>
                <span class="hero-tag">{source_count} Source{'s' if source_count != 1 else ''}</span>
                <span class="hero-tag">ETL Pipeline</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stat_bar(df: pd.DataFrame) -> None:
    total = len(df)
    active = int((df["status"] == "active").sum()) if "status" in df.columns else 0
    remote = int(df["remote_flag"].sum()) if "remote_flag" in df.columns else 0
    companies = df["company"].nunique() if "company" in df.columns else 0
    rate = f"{active / total * 100:.0f}%" if total > 0 else "—"

    st.markdown(
        f"""
        <div class="stat-bar">
            <div class="stat-item">
                <div class="stat-num">{total:,}</div>
                <div class="stat-label">Total records</div>
            </div>
            <div class="stat-item">
                <div class="stat-num accent">{active:,}</div>
                <div class="stat-label">Active listings</div>
            </div>
            <div class="stat-item">
                <div class="stat-num">{remote:,}</div>
                <div class="stat-label">Remote roles</div>
            </div>
            <div class="stat-item">
                <div class="stat-num">{companies:,}</div>
                <div class="stat-label">Companies</div>
            </div>
            <div class="stat-item">
                <div class="stat-num">{rate}</div>
                <div class="stat-label">Completeness</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.markdown("## ◌ JobOS")
    st.sidebar.caption("Filter the extracted dataset.")
    st.sidebar.divider()

    filtered = df.copy()

    if "source" in filtered.columns:
        sources = sorted(filtered["source"].dropna().unique().tolist())
        sel = st.sidebar.multiselect("Source", options=sources, default=sources)
        filtered = filtered[filtered["source"].isin(sel)]

    if "status" in filtered.columns:
        statuses = sorted(filtered["status"].dropna().unique().tolist())
        sel = st.sidebar.multiselect("Status", options=statuses, default=statuses)
        filtered = filtered[filtered["status"].isin(sel)]

    if "seniority_level" in filtered.columns:
        seniorities = sorted(filtered["seniority_level"].dropna().unique().tolist())
        sel = st.sidebar.multiselect("Seniority", options=seniorities, default=seniorities)
        if sel:
            filtered = filtered[filtered["seniority_level"].isin(sel)]

    query = st.sidebar.text_input("Search title / company")
    if query:
        q = query.lower()
        filtered = filtered[
            filtered["title"].fillna("").str.lower().str.contains(q)
            | filtered["company"].fillna("").str.lower().str.contains(q)
        ]

    st.sidebar.divider()
    st.sidebar.caption(f"{len(filtered):,} of {len(df):,} records shown")

    return filtered


def kpi_card(label: str, value: object, note: str, color: str = "") -> str:
    cls = f"kpi-value {color}" if color else "kpi-value"
    return f"""
    <div class="kpi">
        <div class="kpi-label">{label}</div>
        <div class="{cls}">{value}</div>
        <div class="kpi-note">{note}</div>
    </div>
    """


def render_kpis(df: pd.DataFrame) -> None:
    total = len(df)
    active = int((df["status"] == "active").sum()) if "status" in df.columns else 0
    incomplete = int((df["status"] == "incomplete").sum()) if "status" in df.columns else 0
    remote = int(df["remote_flag"].sum()) if "remote_flag" in df.columns else 0

    html = (
        '<div class="kpi-grid">'
        + kpi_card("Total jobs", f"{total:,}", "After cleaning & dedup")
        + kpi_card("Active", f"{active:,}", "Ready for analysis", "accent")
        + kpi_card("Incomplete", f"{incomplete:,}", "Missing critical fields", "warn")
        + kpi_card("Remote", f"{remote:,}", "Remote-friendly roles", "info")
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def section_header(title: str, subtitle: str = "") -> None:
    sub_html = f'<span class="sec-count">{subtitle}</span>' if subtitle else ""
    st.markdown(
        f'<div class="sec-header"><span class="sec-title">{title}</span>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def chart_card_open() -> None:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)


def chart_card_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_overview_charts(df: pd.DataFrame) -> None:
    col1, col2 = st.columns(2)

    with col1:
        chart_card_open()
        section_header("Top job titles", "top 10 by frequency")
        if not df.empty and "title" in df.columns:
            st.bar_chart(df["title"].fillna("Unknown").value_counts().head(10))
        else:
            st.info("No title data.")
        chart_card_close()

    with col2:
        chart_card_open()
        section_header("Top hiring companies", "top 10 by postings")
        if not df.empty and "company" in df.columns:
            st.bar_chart(df["company"].fillna("Unknown").value_counts().head(10))
        else:
            st.info("No company data.")
        chart_card_close()

    col3, col4 = st.columns(2)

    with col3:
        chart_card_open()
        section_header("Remote vs on-site")
        if not df.empty and "remote_flag" in df.columns:
            counts = (
                df["remote_flag"]
                .map({True: "Remote", False: "On-site / Unspecified"})
                .value_counts()
            )
            st.bar_chart(counts)
        else:
            st.info("No remote data.")
        chart_card_close()

    with col4:
        chart_card_open()
        section_header("New listings over time", "by first-seen date")
        if not df.empty and "first_seen" in df.columns:
            daily = (
                df.dropna(subset=["first_seen"])
                .assign(d=lambda x: x["first_seen"].dt.date)
                .groupby("d")
                .size()
            )
            st.line_chart(daily)
        else:
            st.info("No date data.")
        chart_card_close()


def render_jobs_table(df: pd.DataFrame) -> None:
    section_header("Clean job records", f"{len(df):,} results")

    display_cols = [
        "title", "company", "seniority_level", "region", "remote_flag",
        "salary_min", "salary_max", "salary_currency", "date_posted", "source", "status", "url",
    ]
    available = [c for c in display_cols if c in df.columns]
    st.dataframe(df[available], use_container_width=True, hide_index=True)

    st.download_button(
        label="Download filtered CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="filtered_jobs.csv",
        mime="text/csv",
    )


def render_salary_section(df: pd.DataFrame) -> None:
    section_header("Salary breakdown", "by role where data available")

    if df.empty or "salary_midpoint" not in df.columns:
        st.info("No salary data available.")
        return

    salary_df = df.dropna(subset=["salary_midpoint"]).copy()
    if salary_df.empty:
        st.info("No salary data in current records.")
        return

    summary = (
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

    st.dataframe(summary, use_container_width=True, hide_index=True)


def health_row(label: str, value: str, status: str) -> str:
    dot_cls = {"green": "dot-green", "amber": "dot-amber", "red": "dot-red"}.get(status, "dot-green")
    return f"""
    <div class="health-row">
        <span class="health-dot {dot_cls}"></span>
        <span class="health-field">{label}</span>
        <span class="health-val">{value}</span>
    </div>
    """


def render_pipeline_health(df: pd.DataFrame) -> None:
    section_header("Pipeline health")

    total = len(df)
    if total == 0:
        st.info("No records available.")
        return

    incomplete = int((df["status"] == "incomplete").sum()) if "status" in df.columns else 0
    completeness = (total - incomplete) / total * 100 if total else 0

    # KPI row
    source_count = df["source"].nunique() if "source" in df.columns else 0
    html = (
        '<div class="kpi-grid">'
        + kpi_card("Total records", f"{total:,}", "In current pipeline run")
        + kpi_card("Completeness", f"{completeness:.1f}%", "Valid record rate", "accent" if completeness > 80 else "warn")
        + kpi_card("Incomplete", f"{incomplete:,}", "Missing critical fields", "warn" if incomplete else "")
        + kpi_card("Sources", f"{source_count}", "Active data sources")
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        chart_card_open()
        section_header("Field completeness")

        missing_title = int(df["title"].isna().sum()) if "title" in df.columns else 0
        missing_company = int(df["company"].isna().sum()) if "company" in df.columns else 0
        missing_url = int(df["url"].isna().sum()) if "url" in df.columns else 0

        def dot_status(missing: int) -> str:
            if missing == 0:
                return "green"
            elif missing / total < 0.1:
                return "amber"
            return "red"

        rows = (
            health_row("Title", f"{missing_title:,} missing", dot_status(missing_title))
            + health_row("Company", f"{missing_company:,} missing", dot_status(missing_company))
            + health_row("URL", f"{missing_url:,} missing", dot_status(missing_url))
        )
        st.markdown(rows, unsafe_allow_html=True)
        chart_card_close()

    with col2:
        chart_card_open()
        section_header("Records per source")
        if "source" in df.columns:
            st.bar_chart(df["source"].fillna("Unknown").value_counts())
        else:
            st.info("No source data.")
        chart_card_close()

    st.divider()
    section_header("Recent records", "last 20 by pipeline date")

    recent_cols = ["title", "company", "source", "status", "first_seen", "last_seen"]
    available = [c for c in recent_cols if c in df.columns]
    recent = df.sort_values("last_seen", ascending=False).head(20) if "last_seen" in df.columns else df.head(20)
    st.dataframe(recent[available], use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    inject_css()

    df = load_data()

    filtered_df = render_sidebar_filters(df) if not df.empty else df

    render_hero(filtered_df)
    render_stat_bar(filtered_df)

    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)

    if df.empty:
        st.warning(
            "No job data found. Run `python main.py` locally first, "
            "or include `output/jobs_clean.csv` in the deployed repository."
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    tab_overview, tab_jobs, tab_salary, tab_pipeline = st.tabs(
        ["Overview", "Jobs explorer", "Salary analysis", "Pipeline health"]
    )

    with tab_overview:
        st.markdown("<br>", unsafe_allow_html=True)
        render_kpis(filtered_df)
        render_overview_charts(filtered_df)

    with tab_jobs:
        render_jobs_table(filtered_df)

    with tab_salary:
        render_salary_section(filtered_df)

    with tab_pipeline:
        render_pipeline_health(filtered_df)

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()