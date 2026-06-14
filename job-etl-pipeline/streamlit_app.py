"""
streamlit_app.py — Modern Streamlit dashboard for Job Market ETL Pipeline.

UI style:
- "Pipeline blueprint" hero with a build-status badge and an ETL stage stepper
- Live status bar summarizing the active dataset
- KPI cards with semantic accent colors
- Tabbed dashboard layout (Overview, Jobs Explorer, Salary Analysis, Pipeline Health)
- Altair charts themed to match the dashboard palette
- Clean job explorer with rich column formatting (links, currency, checkboxes)
- Salary analysis with summary table + median salary chart
- Pipeline health checks with data-quality visuals
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import altair as alt
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
    page_title="JobOS — Job Market ETL Dashboard",
    page_icon="🧭",
    layout="wide",
)


# ---------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------

INK = "#1C2521"
INK_SOFT = "#5B6660"
PRIMARY = "#2F5D50"
PRIMARY_DARK = "#16332B"
ACCENT = "#E0A23B"
SLATE = "#5E8A99"
SAND = "#D9D4C5"
DANGER = "#C2604A"
SUCCESS = "#5DA37E"
LINE = "#E4E1D8"

PIPELINE_STAGES = [
    ("01", "Scrape", "Pull raw postings from job boards"),
    ("02", "Normalize", "Standardize titles, locations & salaries"),
    ("03", "Deduplicate", "Collapse repeat listings across sources"),
    ("04", "Store", "Persist clean records to SQLite"),
    ("05", "Report", "Surface trends in this dashboard"),
]


# ---------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------

def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

        :root {
            --bg: #f6f5f0;
            --surface: #ffffff;
            --ink: #1c2521;
            --ink-soft: #5b6660;
            --ink-faint: #97998f;
            --line: #e4e1d8;
            --primary: #2f5d50;
            --primary-dark: #16332b;
            --accent: #e0a23b;
            --danger: #c2604a;
        }

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* App background: subtle dot-grid "blueprint" texture */
        .stApp {
            background-color: var(--bg);
            background-image: radial-gradient(circle, rgba(47, 93, 80, 0.10) 1px, transparent 1px);
            background-size: 24px 24px;
            color: var(--ink);
        }

        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 3rem;
            max-width: 1440px;
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header[data-testid="stHeader"] {background: transparent;}

        h1, h2, h3, h4, h5, h6 {
            font-family: 'Sora', sans-serif;
            color: var(--ink);
        }

        p, span, label, div {
            color: inherit;
        }

        a:focus-visible, button:focus-visible, input:focus-visible {
            outline: 2px solid var(--accent);
            outline-offset: 2px;
        }

        /* ============ HERO ============ */
        .hero {
            position: relative;
            border-radius: 20px;
            padding: 40px 44px 32px;
            background: linear-gradient(140deg, var(--primary-dark) 0%, var(--primary) 100%);
            color: #f3f1e9;
            margin-bottom: 28px;
            overflow: hidden;
            box-shadow: 0 16px 40px rgba(22, 51, 43, 0.25);
        }

        .hero::before {
            content: "";
            position: absolute;
            inset: 0;
            background-image:
                linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px);
            background-size: 40px 40px;
            pointer-events: none;
        }

        .hero-top {
            position: relative;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 40px;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 10px;
            font-family: 'Sora', sans-serif;
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.3px;
            color: #ffffff;
        }

        .brand-dot {
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: var(--accent);
        }

        @media (prefers-reduced-motion: no-preference) {
            .brand-dot { animation: pulse 2.4s infinite; }
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(224, 162, 59, 0.55); }
            70% { box-shadow: 0 0 0 8px rgba(224, 162, 59, 0); }
            100% { box-shadow: 0 0 0 0 rgba(224, 162, 59, 0); }
        }

        .build-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            letter-spacing: 0.4px;
            padding: 8px 16px;
            border-radius: 999px;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.18);
            color: #d8f0e4;
        }

        .build-badge .dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #6fcf97;
        }

        .hero-title {
            position: relative;
            max-width: 760px;
            font-family: 'Sora', sans-serif;
            font-size: 46px;
            line-height: 1.08;
            font-weight: 800;
            letter-spacing: -1.5px;
            margin-bottom: 14px;
            color: #ffffff;
        }

        .hero-subtitle {
            position: relative;
            max-width: 640px;
            color: rgba(243, 241, 233, 0.78);
            font-size: 16px;
            line-height: 1.6;
            margin-bottom: 36px;
        }

        /* ETL stage stepper */
        .pipeline-strip {
            position: relative;
            display: flex;
            align-items: flex-start;
        }

        .stage {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            min-width: 110px;
        }

        .stage-node {
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 600;
            width: 34px;
            height: 34px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.10);
            border: 1px solid rgba(255,255,255,0.30);
            color: #f3f1e9;
            margin-bottom: 10px;
        }

        .stage-label {
            font-family: 'Sora', sans-serif;
            font-size: 14px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 4px;
        }

        .stage-desc {
            font-size: 12px;
            line-height: 1.4;
            color: rgba(243, 241, 233, 0.62);
            max-width: 135px;
        }

        .stage-connector {
            flex: 1;
            height: 1px;
            background: rgba(255,255,255,0.25);
            margin-top: 17px;
            min-width: 16px;
        }

        @media (max-width: 1100px) {
            .pipeline-strip { flex-direction: column; gap: 16px; }
            .stage-connector { display: none; }
            .hero-title { font-size: 34px; }
        }

        /* ============ STATUS BAR ============ */
        .status-bar {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 28px;
        }

        .status-chip {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 9px 16px;
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 999px;
            font-size: 13px;
            font-family: 'JetBrains Mono', monospace;
            color: var(--ink-soft);
            box-shadow: 0 1px 2px rgba(28, 37, 33, 0.03);
        }

        .status-chip strong {
            font-family: 'Sora', sans-serif;
            font-weight: 700;
            color: var(--ink);
        }

        .status-chip .chip-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        /* ============ KPI CARDS ============ */
        .kpi-card {
            background: var(--surface);
            border: 1px solid var(--line);
            border-top: 3px solid var(--accent-color, var(--primary));
            border-radius: 10px;
            padding: 20px 22px;
            box-shadow: 0 4px 16px rgba(28, 37, 33, 0.04);
            min-height: 132px;
            margin-bottom: 12px;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }

        .kpi-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(28, 37, 33, 0.08);
        }

        .kpi-label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: var(--ink-faint);
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin-bottom: 14px;
            font-weight: 600;
        }

        .kpi-value {
            font-family: 'Sora', sans-serif;
            font-size: 34px;
            line-height: 1;
            font-weight: 800;
            color: var(--ink);
            letter-spacing: -1px;
        }

        .kpi-note {
            font-size: 12.5px;
            color: var(--ink-soft);
            margin-top: 10px;
        }

        /* ============ SECTION HEADERS ============ */
        .section-title {
            font-family: 'Sora', sans-serif;
            font-size: 21px;
            font-weight: 700;
            letter-spacing: -0.4px;
            margin-bottom: 4px;
            color: var(--ink);
        }

        .section-subtitle {
            font-size: 13px;
            color: var(--ink-soft);
            margin-bottom: 16px;
        }

        .chart-caption {
            text-align: center;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12.5px;
            color: var(--ink-soft);
            margin-top: 4px;
        }

        /* ============ TABS ============ */
        div[data-testid="stTabs"] {
            margin-top: 12px;
        }

        div[data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 6px;
            border-bottom: 1px solid var(--line);
        }

        button[data-baseweb="tab"] {
            background: transparent !important;
            border: none !important;
            padding: 12px 4px !important;
            margin-right: 26px !important;
            border-radius: 0 !important;
            font-weight: 600 !important;
        }

        button[data-baseweb="tab"] p {
            font-family: 'Sora', sans-serif !important;
            color: var(--ink-soft) !important;
            font-weight: 600 !important;
            font-size: 14.5px !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            border-bottom: 2px solid var(--primary) !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] p {
            color: var(--ink) !important;
        }

        /* ============ DATAFRAME ============ */
        div[data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid var(--line);
        }

        /* ============ SIDEBAR ============ */
        section[data-testid="stSidebar"] {
            background: var(--primary-dark);
        }

        section[data-testid="stSidebar"] * {
            color: #eef3f0 !important;
        }

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {
            font-family: 'Sora', sans-serif !important;
        }

        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] textarea {
            color: var(--ink) !important;
            background: #ffffff !important;
            border-radius: 6px !important;
        }

        section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
            background: #ffffff !important;
            border-radius: 6px !important;
        }

        section[data-testid="stSidebar"] div[data-baseweb="select"] span,
        section[data-testid="stSidebar"] div[data-baseweb="select"] div {
            color: var(--ink) !important;
        }

        section[data-testid="stSidebar"] [data-baseweb="tag"] {
            background: var(--accent) !important;
        }

        section[data-testid="stSidebar"] [data-baseweb="tag"] span {
            color: var(--primary-dark) !important;
        }

        .sidebar-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 2px;
        }

        .sidebar-header .title {
            font-family: 'Sora', sans-serif;
            font-weight: 700;
            font-size: 18px;
        }

        .sidebar-result {
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 8px;
            padding: 10px 12px;
            margin-top: 8px;
            line-height: 1.5;
        }

        section[data-testid="stSidebar"] .stButton button {
            width: 100%;
            background: rgba(255,255,255,0.06) !important;
            border: 1px solid rgba(255,255,255,0.18) !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
            color: #eef3f0 !important;
        }

        section[data-testid="stSidebar"] .stButton button:hover {
            border-color: var(--accent) !important;
            color: var(--accent) !important;
        }

        /* ============ DOWNLOAD BUTTON ============ */
        .stDownloadButton button {
            background: var(--primary);
            color: #ffffff;
            border-radius: 6px;
            border: none;
            padding: 10px 18px;
            font-weight: 600;
            font-family: 'Sora', sans-serif;
        }

        .stDownloadButton button:hover {
            background: var(--primary-dark);
            color: #ffffff;
        }

        hr {
            border-color: var(--line);
            margin-top: 28px;
            margin-bottom: 28px;
        }

        /* ============ EMPTY STATES ============ */
        .empty-state {
            border: 1px dashed var(--line);
            border-radius: 10px;
            padding: 28px;
            text-align: center;
            color: var(--ink-soft);
            background: var(--surface);
        }

        .empty-state code {
            background: #efece2;
            color: var(--ink);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 12.5px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_jobs_from_sqlite(db_path: str) -> pd.DataFrame:
    """
    Load jobs from SQLite database.
    """
    query = """
        SELECT
            id,
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
        WHERE status IN ('active', 'incomplete')
        ORDER BY last_seen DESC, id DESC;
    """

    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn)

    return prepare_dataframe(df)


@st.cache_data(show_spinner=False)
def load_jobs_from_csv(csv_path: str) -> pd.DataFrame:
    """
    Load jobs from CSV fallback.
    """
    df = pd.read_csv(csv_path)
    return prepare_dataframe(df)


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare data types for dashboarding.
    """
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

    if "status" in df.columns:
        status_icons = {"active": "✅ Active", "incomplete": "⚠️ Incomplete"}
        df["status_display"] = df["status"].map(status_icons)
        df["status_display"] = df["status_display"].fillna(
            df["status"].fillna("Unknown").astype(str).str.title()
        )

    return df


def load_data() -> pd.DataFrame:
    """
    Load data from SQLite first, then CSV fallback paths.

    Uses APP_DIR so Streamlit Cloud can find files even when the app
    is deployed from a subfolder.
    """
    if DB_PATH.exists():
        return load_jobs_from_sqlite(str(DB_PATH))

    for csv_path in CSV_FALLBACK_PATHS:
        if csv_path.exists():
            return load_jobs_from_csv(str(csv_path))

    return pd.DataFrame()


# ---------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------

def _style_chart(chart: alt.Chart, height: int = 280) -> alt.Chart:
    """
    Apply shared theming to an Altair chart so every chart matches
    the dashboard's palette and type system.
    """
    return (
        chart.properties(height=height)
        .configure_view(strokeWidth=0)
        .configure_axis(
            gridColor=LINE,
            domainColor=LINE,
            tickColor=LINE,
            labelColor=INK_SOFT,
            titleColor=INK_SOFT,
            labelFont="Inter",
            titleFont="Inter",
            labelFontSize=11,
            titleFontSize=11,
            titleFontWeight="normal",
        )
        .configure_legend(
            labelFont="Inter",
            titleFont="Inter",
            labelColor=INK_SOFT,
            titleColor=INK_SOFT,
            labelFontSize=11,
        )
    )


def _empty(message: str) -> None:
    st.markdown(f'<div class="empty-state">{message}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------

def render_hero(df: pd.DataFrame) -> None:
    if "last_seen" in df.columns and not df["last_seen"].dropna().empty:
        last_run = df["last_seen"].max().strftime("%b %d, %Y")
    else:
        last_run = "—"

    stages_html = []
    for i, (num, label, desc) in enumerate(PIPELINE_STAGES):
        stages_html.append(
            f"""
            <div class="stage">
                <div class="stage-node">{num}</div>
                <div class="stage-label">{label}</div>
                <div class="stage-desc">{desc}</div>
            </div>
            """
        )
        if i < len(PIPELINE_STAGES) - 1:
            stages_html.append('<div class="stage-connector"></div>')

    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-top">
                <div class="brand"><span class="brand-dot"></span> JobOS</div>
                <div class="build-badge"><span class="dot"></span> Pipeline run · {last_run}</div>
            </div>
            <div class="hero-title">Automated Job Market Intelligence</div>
            <div class="hero-subtitle">
                An end-to-end ETL pipeline that scrapes job postings, normalizes messy
                fields, deduplicates listings across sources, and stores clean records
                in SQLite — surfaced below for analysis.
            </div>
            <div class="pipeline-strip">
                {''.join(stages_html)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_bar(df: pd.DataFrame) -> None:
    total = len(df)
    source_count = df["source"].nunique() if "source" in df.columns else 0
    company_count = df["company"].nunique() if "company" in df.columns else 0
    remote_count = int(df["remote_flag"].sum()) if "remote_flag" in df.columns else 0
    active_count = int((df["status"] == "active").sum()) if "status" in df.columns else 0

    chips = [
        (PRIMARY, "Showing", f"{total:,} jobs"),
        (ACCENT, "Sources", f"{source_count}"),
        (SLATE, "Companies", f"{company_count}"),
        (PRIMARY, "Remote", f"{remote_count}"),
        (SUCCESS, "Active", f"{active_count}"),
    ]

    chip_html = "".join(
        f'<div class="status-chip"><span class="chip-dot" style="background:{color};"></span>'
        f"{label}: <strong>{value}</strong></div>"
        for color, label, value in chips
    )

    st.markdown(f'<div class="status-bar">{chip_html}</div>', unsafe_allow_html=True)


def render_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sidebar filters for source, status, seniority, and search keyword.
    """
    st.sidebar.markdown(
        """
        <div class="sidebar-header">
            <span style="font-size: 18px;">⌁</span>
            <span class="title">Filters</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.caption("Refine the extracted job dataset.")

    if st.sidebar.button("Reset filters"):
        for key in ("filter_source", "filter_status", "filter_seniority", "filter_search"):
            st.session_state.pop(key, None)
        st.rerun()

    filtered = df.copy()

    if "source" in filtered.columns:
        sources = sorted(filtered["source"].dropna().unique().tolist())
        selected_sources = st.sidebar.multiselect(
            "Source",
            options=sources,
            default=sources,
            key="filter_source",
        )
        filtered = filtered[filtered["source"].isin(selected_sources)]

    if "status" in filtered.columns:
        statuses = sorted(filtered["status"].dropna().unique().tolist())
        selected_statuses = st.sidebar.multiselect(
            "Status",
            options=statuses,
            default=statuses,
            key="filter_status",
        )
        filtered = filtered[filtered["status"].isin(selected_statuses)]

    if "seniority_level" in filtered.columns:
        seniorities = sorted(filtered["seniority_level"].dropna().unique().tolist())
        selected_seniorities = st.sidebar.multiselect(
            "Seniority",
            options=seniorities,
            default=seniorities,
            key="filter_seniority",
        )

        if selected_seniorities:
            filtered = filtered[filtered["seniority_level"].isin(selected_seniorities)]

    search_text = st.sidebar.text_input("Search title or company", key="filter_search")

    if search_text:
        search_lower = search_text.lower()
        filtered = filtered[
            filtered["title"].fillna("").str.lower().str.contains(search_lower)
            | filtered["company"].fillna("").str.lower().str.contains(search_lower)
        ]

    st.sidebar.markdown(
        f"""
        <div class="sidebar-result">
            Showing <strong>{len(filtered):,}</strong> of <strong>{len(df):,}</strong> records
        </div>
        """,
        unsafe_allow_html=True,
    )

    return filtered


def render_kpi_cards(cards: list[tuple[str, object, str, str]]) -> None:
    """
    Render reusable KPI cards.

    Each card is (label, value, note, accent_color).
    """
    columns = st.columns(len(cards))

    for col, (label, value, note, color) in zip(columns, cards):
        with col:
            st.markdown(
                f"""
                <div class="kpi-card" style="--accent-color: {color};">
                    <div class="kpi-label">{label}</div>
                    <div class="kpi-value">{value}</div>
                    <div class="kpi-note">{note}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_kpis(df: pd.DataFrame) -> None:
    """
    Render overview KPI cards.
    """
    total_jobs = len(df)
    active_jobs = int((df["status"] == "active").sum()) if "status" in df else 0
    incomplete_jobs = int((df["status"] == "incomplete").sum()) if "status" in df else 0
    remote_jobs = int(df["remote_flag"].sum()) if "remote_flag" in df else 0

    cards = [
        ("Total Jobs", f"{total_jobs:,}", "Records available after cleaning", PRIMARY),
        ("Active Jobs", f"{active_jobs:,}", "Valid records ready for analysis", SUCCESS),
        (
            "Incomplete",
            f"{incomplete_jobs:,}",
            "Missing critical fields",
            DANGER if incomplete_jobs else PRIMARY,
        ),
        ("Remote Jobs", f"{remote_jobs:,}", "Remote-friendly listings", ACCENT),
    ]

    render_kpi_cards(cards)


def render_overview_charts(df: pd.DataFrame) -> None:
    """
    Render overview chart sections.
    """
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="section-title">Top Job Titles</div>
            <div class="section-subtitle">Most frequent normalized job titles.</div>
            """,
            unsafe_allow_html=True,
        )

        if not df.empty and "title" in df.columns:
            counts = df["title"].fillna("Unknown").value_counts().head(10).reset_index()
            counts.columns = ["title", "count"]

            chart = (
                alt.Chart(counts)
                .mark_bar(color=PRIMARY, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
                .encode(
                    x=alt.X("count:Q", title="Postings"),
                    y=alt.Y("title:N", sort="-x", title=None),
                    tooltip=[
                        alt.Tooltip("title:N", title="Title"),
                        alt.Tooltip("count:Q", title="Postings"),
                    ],
                )
            )
            st.altair_chart(_style_chart(chart, height=320), width="stretch")
        else:
            _empty("No title data available.")

    with col2:
        st.markdown(
            """
            <div class="section-title">Top Hiring Companies</div>
            <div class="section-subtitle">Companies with the most extracted postings.</div>
            """,
            unsafe_allow_html=True,
        )

        if not df.empty and "company" in df.columns:
            counts = df["company"].fillna("Unknown").value_counts().head(10).reset_index()
            counts.columns = ["company", "count"]

            chart = (
                alt.Chart(counts)
                .mark_bar(color=SLATE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
                .encode(
                    x=alt.X("count:Q", title="Postings"),
                    y=alt.Y("company:N", sort="-x", title=None),
                    tooltip=[
                        alt.Tooltip("company:N", title="Company"),
                        alt.Tooltip("count:Q", title="Postings"),
                    ],
                )
            )
            st.altair_chart(_style_chart(chart, height=320), width="stretch")
        else:
            _empty("No company data available.")

    st.divider()

    col3, col4 = st.columns(2)

    with col3:
        st.markdown(
            """
            <div class="section-title">Remote Breakdown</div>
            <div class="section-subtitle">Remote versus on-site or unspecified roles.</div>
            """,
            unsafe_allow_html=True,
        )

        if not df.empty and "remote_flag" in df.columns:
            counts = (
                df["remote_flag"]
                .map({True: "Remote", False: "On-site / Unspecified"})
                .value_counts()
                .reset_index()
            )
            counts.columns = ["label", "count"]

            chart = (
                alt.Chart(counts)
                .mark_arc(innerRadius=70, outerRadius=110)
                .encode(
                    theta=alt.Theta("count:Q"),
                    color=alt.Color(
                        "label:N",
                        scale=alt.Scale(
                            domain=["Remote", "On-site / Unspecified"],
                            range=[PRIMARY, SAND],
                        ),
                        legend=alt.Legend(title=None, orient="bottom"),
                    ),
                    tooltip=[
                        alt.Tooltip("label:N", title="Type"),
                        alt.Tooltip("count:Q", title="Postings"),
                    ],
                )
            )
            st.altair_chart(_style_chart(chart, height=300), width="stretch")

            total = int(counts["count"].sum())
            remote_total = int(
                counts.loc[counts["label"] == "Remote", "count"].sum()
            )
            remote_pct = (remote_total / total * 100) if total else 0
            st.markdown(
                f'<div class="chart-caption">{remote_pct:.0f}% of listings are remote</div>',
                unsafe_allow_html=True,
            )
        else:
            _empty("No remote data available.")

    with col4:
        st.markdown(
            """
            <div class="section-title">New Jobs Over Time</div>
            <div class="section-subtitle">Listings by first-seen pipeline date.</div>
            """,
            unsafe_allow_html=True,
        )

        if not df.empty and "first_seen" in df.columns and not df["first_seen"].dropna().empty:
            daily = (
                df.dropna(subset=["first_seen"])
                .assign(date=lambda x: x["first_seen"].dt.date)
                .groupby("date")
                .size()
                .reset_index(name="count")
            )

            chart = (
                alt.Chart(daily)
                .mark_area(
                    line={"color": PRIMARY},
                    color=alt.Gradient(
                        gradient="linear",
                        stops=[
                            alt.GradientStop(color="#ffffff", offset=0),
                            alt.GradientStop(color=PRIMARY, offset=1),
                        ],
                        x1=1,
                        x2=1,
                        y1=1,
                        y2=0,
                    ),
                    opacity=0.35,
                )
                .encode(
                    x=alt.X("date:T", title=None),
                    y=alt.Y("count:Q", title="New listings"),
                    tooltip=[
                        alt.Tooltip("date:T", title="Date"),
                        alt.Tooltip("count:Q", title="New listings"),
                    ],
                )
            )
            st.altair_chart(_style_chart(chart, height=300), width="stretch")
        else:
            _empty("No date data available.")


def render_salary_section(df: pd.DataFrame) -> None:
    """
    Render salary summary table and median salary chart.
    """
    st.markdown(
        """
        <div class="section-title">Salary Summary</div>
        <div class="section-subtitle">
            Salary distribution by role where salary fields are available.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if df.empty or "salary_midpoint" not in df.columns:
        _empty("No salary data available.")
        return

    salary_df = df.dropna(subset=["salary_midpoint"]).copy()

    if salary_df.empty:
        _empty("Salary data not available in current records.")
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

    table_col, chart_col = st.columns([3, 2])

    with table_col:
        st.dataframe(
            summary,
            width="stretch",
            hide_index=True,
            column_config={
                "title": st.column_config.TextColumn("Title"),
                "salary_currency": st.column_config.TextColumn("Currency"),
                "count": st.column_config.NumberColumn("Postings", format="%d"),
                "salary_min": st.column_config.NumberColumn("Min", format="%.0f"),
                "salary_median": st.column_config.NumberColumn("Median", format="%.0f"),
                "salary_max": st.column_config.NumberColumn("Max", format="%.0f"),
            },
        )

    with chart_col:
        st.markdown(
            """
            <div class="section-subtitle" style="margin-bottom: 8px;">
                Median salary — top roles by posting volume.
            </div>
            """,
            unsafe_allow_html=True,
        )

        top_roles = summary.head(10)

        chart = (
            alt.Chart(top_roles)
            .mark_bar(color=ACCENT, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                x=alt.X("salary_median:Q", title="Median salary"),
                y=alt.Y("title:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("title:N", title="Title"),
                    alt.Tooltip("salary_median:Q", title="Median salary", format=",.0f"),
                ],
            )
        )
        st.altair_chart(_style_chart(chart, height=320), width="stretch")


def render_jobs_table(df: pd.DataFrame) -> None:
    """
    Render clean job records table.
    """
    st.markdown(
        """
        <div class="section-title">Clean Job Records</div>
        <div class="section-subtitle">
            Final cleaned and deduplicated records available for export.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if df.empty:
        _empty("No jobs match the current filters.")
        return

    display_columns = [
        "title",
        "company",
        "seniority_level",
        "region",
        "remote_flag",
        "salary_min",
        "salary_max",
        "salary_currency",
        "date_posted",
        "source",
        "status_display",
        "url",
    ]

    available_columns = [col for col in display_columns if col in df.columns]

    column_config = {
        "title": st.column_config.TextColumn("Title", width="medium"),
        "company": st.column_config.TextColumn("Company"),
        "seniority_level": st.column_config.TextColumn("Seniority"),
        "region": st.column_config.TextColumn("Region"),
        "remote_flag": st.column_config.CheckboxColumn("Remote", disabled=True),
        "salary_min": st.column_config.NumberColumn("Min Salary", format="%.0f"),
        "salary_max": st.column_config.NumberColumn("Max Salary", format="%.0f"),
        "salary_currency": st.column_config.TextColumn("Currency"),
        "date_posted": st.column_config.DateColumn("Posted", format="MMM D, YYYY"),
        "source": st.column_config.TextColumn("Source"),
        "status_display": st.column_config.TextColumn("Status"),
        "url": st.column_config.LinkColumn("Listing"),
    }
    active_config = {key: value for key, value in column_config.items() if key in available_columns}

    st.dataframe(
        df[available_columns],
        width="stretch",
        hide_index=True,
        column_config=active_config,
    )

    export_df = df.drop(columns=["salary_midpoint", "status_display"], errors="ignore")
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download Filtered CSV",
        data=csv_bytes,
        file_name="filtered_jobs.csv",
        mime="text/csv",
    )


def render_pipeline_health(df: pd.DataFrame) -> None:
    """
    Render pipeline quality and operational health indicators.
    """
    st.markdown(
        """
        <div class="section-title">Pipeline Health</div>
        <div class="section-subtitle">
            Data quality, completeness, and source-level distribution.
        </div>
        """,
        unsafe_allow_html=True,
    )

    total_records = len(df)

    if total_records == 0:
        _empty("No records available for pipeline health checks.")
        return

    missing_title = int(df["title"].isna().sum()) if "title" in df.columns else 0
    missing_company = int(df["company"].isna().sum()) if "company" in df.columns else 0
    missing_url = int(df["url"].isna().sum()) if "url" in df.columns else 0

    incomplete_records = (
        int((df["status"] == "incomplete").sum())
        if "status" in df.columns
        else 0
    )

    completeness_rate = (
        ((total_records - incomplete_records) / total_records) * 100
        if total_records
        else 0
    )

    source_count = df["source"].nunique() if "source" in df.columns else 0

    cards = [
        ("Total Records", f"{total_records:,}", "Rows currently available", PRIMARY),
        (
            "Incomplete Records",
            f"{incomplete_records:,}",
            "Missing critical fields",
            DANGER if incomplete_records else PRIMARY,
        ),
        (
            "Completeness Rate",
            f"{completeness_rate:.1f}%",
            "Valid record percentage",
            SUCCESS if completeness_rate >= 90 else ACCENT,
        ),
        ("Sources", f"{source_count}", "Active data sources", SLATE),
    ]

    render_kpi_cards(cards)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="section-title">Missing Critical Fields</div>
            <div class="section-subtitle">
                Records missing title, company, or URL.
            </div>
            """,
            unsafe_allow_html=True,
        )

        missing_df = pd.DataFrame(
            {
                "field": ["title", "company", "url"],
                "missing_count": [missing_title, missing_company, missing_url],
            }
        )

        chart = (
            alt.Chart(missing_df)
            .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                x=alt.X("missing_count:Q", title="Missing records"),
                y=alt.Y("field:N", title=None, sort="-x"),
                color=alt.condition(
                    alt.datum.missing_count > 0,
                    alt.value(DANGER),
                    alt.value(PRIMARY),
                ),
                tooltip=[
                    alt.Tooltip("field:N", title="Field"),
                    alt.Tooltip("missing_count:Q", title="Missing"),
                ],
            )
        )
        st.altair_chart(_style_chart(chart, height=200), width="stretch")

    with col2:
        st.markdown(
            """
            <div class="section-title">Source Distribution</div>
            <div class="section-subtitle">
                Number of records extracted per source.
            </div>
            """,
            unsafe_allow_html=True,
        )

        if "source" in df.columns:
            counts = df["source"].fillna("Unknown").value_counts().reset_index()
            counts.columns = ["source", "count"]

            chart = (
                alt.Chart(counts)
                .mark_bar(color=SLATE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
                .encode(
                    x=alt.X("count:Q", title="Records"),
                    y=alt.Y("source:N", sort="-x", title=None),
                    tooltip=[
                        alt.Tooltip("source:N", title="Source"),
                        alt.Tooltip("count:Q", title="Records"),
                    ],
                )
            )
            st.altair_chart(_style_chart(chart, height=200), width="stretch")
        else:
            _empty("No source information available.")

    st.divider()

    st.markdown(
        """
        <div class="section-title">Recent Records</div>
        <div class="section-subtitle">
            Most recently seen records in the pipeline.
        </div>
        """,
        unsafe_allow_html=True,
    )

    recent_columns = [
        "title",
        "company",
        "source",
        "status_display",
        "first_seen",
        "last_seen",
    ]

    available_columns = [col for col in recent_columns if col in df.columns]

    if "last_seen" in df.columns:
        recent_df = df.sort_values("last_seen", ascending=False).head(20)
    else:
        recent_df = df.head(20)

    st.dataframe(
        recent_df[available_columns],
        width="stretch",
        hide_index=True,
        column_config={
            "title": st.column_config.TextColumn("Title", width="medium"),
            "company": st.column_config.TextColumn("Company"),
            "source": st.column_config.TextColumn("Source"),
            "status_display": st.column_config.TextColumn("Status"),
            "first_seen": st.column_config.DatetimeColumn("First Seen", format="MMM D, YYYY HH:mm"),
            "last_seen": st.column_config.DatetimeColumn("Last Seen", format="MMM D, YYYY HH:mm"),
        },
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    inject_css()

    df = load_data()

    render_hero(df)

    if df.empty:
        _empty(
            "<strong>No job data found yet.</strong><br/>"
            "Run <code>python main.py</code> locally to populate "
            "<code>jobs.db</code>, or include <code>output/jobs_clean.csv</code> "
            "in the deployed repository."
        )
        return

    filtered_df = render_sidebar_filters(df)

    render_status_bar(filtered_df)

    tab_overview, tab_jobs, tab_salary, tab_pipeline = st.tabs(
        [
            "Overview",
            "Jobs Explorer",
            "Salary Analysis",
            "Pipeline Health",
        ]
    )

    with tab_overview:
        render_kpis(filtered_df)

        st.divider()

        render_overview_charts(filtered_df)

    with tab_jobs:
        render_jobs_table(filtered_df)

    with tab_salary:
        render_salary_section(filtered_df)

    with tab_pipeline:
        render_pipeline_health(filtered_df)

    st.markdown(
        """
        <div style="text-align: center; margin-top: 36px; font-family: 'JetBrains Mono', monospace;
                    font-size: 12px; color: var(--ink-faint);">
            JobOS · ETL pipeline for job market data — Streamlit · pandas · SQLite
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()