"""
streamlit_app.py — Modern Streamlit dashboard for Job Market ETL Pipeline.

UI style:
- Dark hero section
- Navigation/filter chips
- KPI cards
- Tabbed dashboard layout
- Clean job explorer
- Salary analysis
- Pipeline health checks
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


DB_PATH = Path("jobs.db")
CSV_FALLBACK_PATHS = [
    Path("output/jobs_clean.csv"),
    Path("jobs_clean.csv"),
]


st.set_page_config(
    page_title="Job Market ETL Dashboard",
    page_icon="📊",
    layout="wide",
)


# ---------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------

def inject_css() -> None:
    st.markdown(
        """
        <style>
        /* App background */
        .stApp {
            background: #f1f1f1;
            color: #111827;
        }

        /* Main container */
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 3rem;
            max-width: 1450px;
        }

        /* Hide Streamlit chrome */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* General text safety */
        h1, h2, h3, h4, h5, h6, p, span, label {
            color: inherit;
        }

        /* Hero section */
        .hero {
            position: relative;
            border-radius: 0px;
            padding: 48px 56px;
            min-height: 260px;
            background:
                linear-gradient(
                    rgba(10, 16, 24, 0.80),
                    rgba(10, 16, 24, 0.80)
                ),
                url("https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=1600&q=80");
            background-size: cover;
            background-position: center;
            color: white;
            margin-bottom: 36px;
            box-shadow: 0 12px 30px rgba(0,0,0,0.12);
        }

        .hero-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 56px;
        }

        .brand {
            font-size: 22px;
            font-weight: 700;
            letter-spacing: -0.4px;
            color: #ffffff;
        }

        .hero-button {
            border: 1px solid rgba(255,255,255,0.75);
            padding: 12px 26px;
            font-size: 14px;
            font-weight: 700;
            background: rgba(255,255,255,0.96);
            color: #111827;
            border-radius: 2px;
        }

        .hero-title {
            max-width: 840px;
            font-size: 52px;
            line-height: 1.02;
            font-weight: 800;
            letter-spacing: -2.5px;
            margin-bottom: 16px;
            color: #ffffff;
        }

        .hero-subtitle {
            max-width: 760px;
            color: rgba(255,255,255,0.82);
            font-size: 17px;
            line-height: 1.55;
        }

        /* Chips */
        .chip-row {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 26px;
        }

        .chip {
            display: inline-block;
            padding: 10px 17px;
            background: #ffffff;
            color: #333333;
            border-radius: 3px;
            font-size: 15px;
            border: 1px solid #e7e7e7;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        }

        .chip-active {
            background: #111827;
            color: #ffffff;
            border-color: #111827;
        }

        /* KPI cards */
        .kpi-card {
            background: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            padding: 24px 24px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.04);
            min-height: 128px;
            margin-bottom: 10px;
        }

        .kpi-label {
            font-size: 13px;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            margin-bottom: 12px;
            font-weight: 700;
        }

        .kpi-value {
            font-size: 38px;
            line-height: 1;
            font-weight: 800;
            color: #111827;
            letter-spacing: -1.5px;
        }

        .kpi-note {
            font-size: 13px;
            color: #6b7280;
            margin-top: 10px;
        }

        /* Section titles */
        .section-title {
            font-size: 25px;
            font-weight: 800;
            letter-spacing: -0.8px;
            margin-bottom: 6px;
            color: #111827;
        }

        .section-subtitle {
            font-size: 14px;
            color: #6b7280;
            margin-bottom: 18px;
        }

        /* Tabs */
        button[data-baseweb="tab"] {
            background: #ffffff !important;
            border: 1px solid #dcdcdc !important;
            padding: 12px 22px !important;
            margin-right: 10px !important;
            border-radius: 3px 3px 0 0 !important;
            font-weight: 700 !important;
            color: #111827 !important;
            min-width: 150px;
        }

        button[data-baseweb="tab"] p {
            color: #111827 !important;
            font-weight: 700 !important;
            font-size: 15px !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            background: #111827 !important;
            color: #ffffff !important;
            border-color: #111827 !important;
            border-bottom: 3px solid #ef4444 !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] p {
            color: #ffffff !important;
        }

        div[data-testid="stTabs"] {
            margin-top: 20px;
        }

        /* Streamlit metric cards fallback */
        div[data-testid="stMetric"] {
            background: #ffffff !important;
            padding: 22px 24px !important;
            border-radius: 5px !important;
            border: 1px solid #e0e0e0 !important;
            box-shadow: 0 6px 18px rgba(0,0,0,0.04) !important;
        }

        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] label p {
            color: #6b7280 !important;
            font-size: 14px !important;
            font-weight: 600 !important;
        }

        div[data-testid="stMetric"] div[data-testid="stMetricValue"],
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] div {
            color: #111827 !important;
            font-size: 36px !important;
            font-weight: 800 !important;
        }

        /* Tables */
        div[data-testid="stDataFrame"] {
            border-radius: 5px;
            overflow: hidden;
            border: 1px solid #e5e7eb;
        }

        /* Sidebar */
        section[data-testid="stSidebar"] {
            background: #111827;
        }

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] span {
            color: #ffffff !important;
        }

        section[data-testid="stSidebar"] input {
            color: #111827 !important;
            background: #ffffff !important;
        }

        section[data-testid="stSidebar"] div[data-baseweb="select"] span {
            color: #111827 !important;
        }

        /* Download button */
        .stDownloadButton button {
            background: #111827;
            color: #ffffff;
            border-radius: 3px;
            border: none;
            padding: 10px 18px;
            font-weight: 700;
        }

        .stDownloadButton button:hover {
            background: #374151;
            color: #ffffff;
        }

        hr {
            margin-top: 32px;
            margin-bottom: 32px;
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

    return df

def load_data() -> pd.DataFrame:
    """
    Load data from SQLite first, then CSV fallback paths.
    """
    if DB_PATH.exists():
        return load_jobs_from_sqlite(str(DB_PATH))

    for csv_path in CSV_FALLBACK_PATHS:
        if csv_path.exists():
            return load_jobs_from_csv(str(csv_path))

    return pd.DataFrame()
# ---------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------

def render_hero() -> None:
    st.markdown(
        """
        <div class="hero">
            <div class="hero-top">
                <div class="brand">◌ JobOS</div>
                <div class="hero-button">ETL Portfolio Project</div>
            </div>
            <div class="hero-title">
                Automated Job Market Intelligence Pipeline
            </div>
            <div class="hero-subtitle">
                A full ETL workflow for scraping job postings, cleaning messy fields,
                deduplicating listings, storing records in SQLite, and generating
                analytical reports.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chips(df: pd.DataFrame) -> None:
    source_count = df["source"].nunique() if "source" in df.columns else 0
    company_count = df["company"].nunique() if "company" in df.columns else 0
    remote_count = int(df["remote_flag"].sum()) if "remote_flag" in df.columns else 0

    st.markdown(
        f"""
        <div class="chip-row">
            <span class="chip chip-active">Overview</span>
            <span class="chip">Sources: {source_count}</span>
            <span class="chip">Companies: {company_count}</span>
            <span class="chip">Remote Jobs: {remote_count}</span>
            <span class="chip">SQLite</span>
            <span class="chip">Pandas Reports</span>
            <span class="chip">Deduplication</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sidebar filters for source, status, seniority, and search keyword.
    """
    st.sidebar.title("Filters")
    st.sidebar.caption("Refine the extracted job dataset.")

    filtered = df.copy()

    if "source" in filtered.columns:
        sources = sorted(filtered["source"].dropna().unique().tolist())
        selected_sources = st.sidebar.multiselect(
            "Source",
            options=sources,
            default=sources,
        )
        filtered = filtered[filtered["source"].isin(selected_sources)]

    if "status" in filtered.columns:
        statuses = sorted(filtered["status"].dropna().unique().tolist())
        selected_statuses = st.sidebar.multiselect(
            "Status",
            options=statuses,
            default=statuses,
        )
        filtered = filtered[filtered["status"].isin(selected_statuses)]

    if "seniority_level" in filtered.columns:
        seniorities = sorted(filtered["seniority_level"].dropna().unique().tolist())
        selected_seniorities = st.sidebar.multiselect(
            "Seniority",
            options=seniorities,
            default=seniorities,
        )

        if selected_seniorities:
            filtered = filtered[filtered["seniority_level"].isin(selected_seniorities)]

    search_text = st.sidebar.text_input("Search title/company")

    if search_text:
        search_lower = search_text.lower()
        filtered = filtered[
            filtered["title"].fillna("").str.lower().str.contains(search_lower)
            | filtered["company"].fillna("").str.lower().str.contains(search_lower)
        ]

    return filtered


def render_kpi_cards(cards: list[tuple[str, object, str]]) -> None:
    """
    Render reusable KPI cards.
    """
    columns = st.columns(len(cards))

    for col, (label, value, note) in zip(columns, cards):
        with col:
            st.markdown(
                f"""
                <div class="kpi-card">
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
        ("Total Jobs", total_jobs, "Records available after cleaning"),
        ("Active Jobs", active_jobs, "Valid records ready for analysis"),
        ("Incomplete", incomplete_jobs, "Missing critical fields"),
        ("Remote Jobs", remote_jobs, "Remote-friendly listings"),
    ]

    render_kpi_cards(cards)


def render_chart_sections(df: pd.DataFrame) -> None:
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
            title_counts = df["title"].fillna("Unknown").value_counts().head(10)
            st.bar_chart(title_counts)
        else:
            st.info("No title data available.")

    with col2:
        st.markdown(
            """
            <div class="section-title">Top Hiring Companies</div>
            <div class="section-subtitle">Companies with the most extracted postings.</div>
            """,
            unsafe_allow_html=True,
        )

        if not df.empty and "company" in df.columns:
            company_counts = df["company"].fillna("Unknown").value_counts().head(10)
            st.bar_chart(company_counts)
        else:
            st.info("No company data available.")

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
            remote_counts = (
                df["remote_flag"]
                .map({True: "Remote", False: "On-site / Unspecified"})
                .value_counts()
            )
            st.bar_chart(remote_counts)
        else:
            st.info("No remote data available.")

    with col4:
        st.markdown(
            """
            <div class="section-title">New Jobs Over Time</div>
            <div class="section-subtitle">Listings by first-seen pipeline date.</div>
            """,
            unsafe_allow_html=True,
        )

        if not df.empty and "first_seen" in df.columns:
            daily_counts = (
                df.dropna(subset=["first_seen"])
                .assign(first_seen_date=lambda x: x["first_seen"].dt.date)
                .groupby("first_seen_date")
                .size()
            )
            st.line_chart(daily_counts)
        else:
            st.info("No date data available.")


def render_salary_section(df: pd.DataFrame) -> None:
    """
    Render salary summary table.
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
        st.info("No salary data available.")
        return

    salary_df = df.dropna(subset=["salary_midpoint"]).copy()

    if salary_df.empty:
        st.info("Salary data not available in current records.")
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
        "status",
        "url",
    ]

    available_columns = [col for col in display_columns if col in df.columns]

    st.dataframe(
        df[available_columns],
        use_container_width=True,
        hide_index=True,
    )

    csv_bytes = df.to_csv(index=False).encode("utf-8")

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
        st.info("No records available for pipeline health checks.")
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
        ("Total Records", total_records, "Rows currently available"),
        ("Incomplete Records", incomplete_records, "Missing critical fields"),
        ("Completeness Rate", f"{completeness_rate:.1f}%", "Valid record percentage"),
        ("Sources", source_count, "Active data sources"),
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

        st.dataframe(missing_df, use_container_width=True, hide_index=True)

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
            source_counts = df["source"].fillna("Unknown").value_counts()
            st.bar_chart(source_counts)
        else:
            st.info("No source information available.")

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
        "status",
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
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    inject_css()
    render_hero()

    df = load_data()

    if df.empty:
        st.warning(
            "No job data found. Run `python main.py` locally first, "
            "or include `output/jobs_clean.csv` in the deployed repository."
        )
        return

    filtered_df = render_sidebar_filters(df)

    render_chips(filtered_df)

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

        render_chart_sections(filtered_df)

    with tab_jobs:
        render_jobs_table(filtered_df)

    with tab_salary:
        render_salary_section(filtered_df)

    with tab_pipeline:
        render_pipeline_health(filtered_df)


if __name__ == "__main__":
    main()