"""
streamlit_app.py — Improved Streamlit dashboard for Job Market ETL Pipeline.

UI/UX improvements:
- CSS variables that respect Streamlit's light/dark theme instead of hardcoded hex
- Removed duplicate stat-bar (metrics now live only in Overview KPIs)
- Simplified hero — leaner, no repeated numbers
- st.metric() for KPI cards so Streamlit handles layout & theming
- Plotly charts instead of bare st.bar_chart / st.line_chart for proper labels/colors
- Better empty state guidance with actionable copy
- Sidebar filters always visible with clear reset affordance
- Cleaner tab structure — Pipeline Health renamed to Data Quality
- Section dividers removed in favour of whitespace
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
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS — uses Streamlit's own CSS variables so light/dark mode both work
# ---------------------------------------------------------------------------

def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* Remove excessive top padding */
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 3rem;
            max-width: 1400px;
        }

        #MainMenu, footer, header { visibility: hidden; }

        /* ── Hero ───────────────────────────────────────────── */
        .hero {
            padding: 36px 0 32px;
            border-bottom: 1px solid rgba(128,128,128,0.15);
            margin-bottom: 28px;
        }

        .hero-eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: #10B981;
            margin-bottom: 16px;
        }

        .hero-dot {
            width: 6px; height: 6px;
            border-radius: 50%;
            background: #10B981;
            display: inline-block;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50%       { opacity: 0.35; }
        }

        .hero-title {
            font-size: 38px;
            font-weight: 800;
            letter-spacing: -1.5px;
            line-height: 1.1;
            /* Inherit theme text color so it works in dark mode */
            color: inherit;
            margin-bottom: 10px;
        }

        .hero-title .accent { color: #10B981; }

        .hero-sub {
            font-size: 14px;
            line-height: 1.65;
            color: var(--text-color, #6B7280);
            opacity: 0.65;
            max-width: 520px;
            margin-bottom: 24px;
        }

        .hero-tags {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .hero-tag {
            padding: 4px 12px;
            border: 1px solid rgba(128,128,128,0.25);
            border-radius: 3px;
            font-size: 11px;
            font-weight: 600;
            color: inherit;
            opacity: 0.55;
            letter-spacing: 0.5px;
        }

        /* ── Section headers ────────────────────────────────── */
        .sec-header {
            display: flex;
            align-items: baseline;
            gap: 10px;
            margin-bottom: 12px;
        }

        .sec-title {
            font-size: 15px;
            font-weight: 700;
            letter-spacing: -0.3px;
            color: inherit;
        }

        .sec-count {
            font-size: 12px;
            font-weight: 500;
            opacity: 0.45;
        }

        /* ── Tabs ───────────────────────────────────────────── */
        button[data-baseweb="tab"] {
            background: transparent !important;
            border: none !important;
            border-bottom: 2px solid transparent !important;
            padding: 10px 16px !important;
            margin-right: 2px !important;
            border-radius: 0 !important;
            font-weight: 600 !important;
            font-size: 13px !important;
            color: rgba(128,128,128,0.8) !important;
            transition: color 0.15s, border-color 0.15s;
        }

        button[data-baseweb="tab"] p {
            color: inherit !important;
            font-weight: inherit !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            color: inherit !important;
            border-bottom-color: #10B981 !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] p {
            color: inherit !important;
        }

        div[role="tabpanel"] { padding-top: 20px; }

        /* ── Table ──────────────────────────────────────────── */
        div[data-testid="stDataFrame"] {
            border-radius: 6px;
            overflow: hidden;
            border: 1px solid rgba(128,128,128,0.18);
        }

        /* ── Sidebar ────────────────────────────────────────── */
        section[data-testid="stSidebar"] {
            border-right: 1px solid rgba(128,128,128,0.18);
        }

        section[data-testid="stSidebar"] > div {
            padding-top: 1.75rem;
        }

        /* ── Download button ────────────────────────────────── */
        .stDownloadButton button {
            border-radius: 4px !important;
            font-weight: 700 !important;
            font-size: 13px !important;
        }

        /* ── Metric cards (st.metric) ───────────────────────── */
        [data-testid="stMetric"] {
            background: rgba(128,128,128,0.05);
            border: 1px solid rgba(128,128,128,0.12);
            border-radius: 8px;
            padding: 16px 18px 14px;
        }

        [data-testid="stMetricLabel"] > div {
            font-size: 11px !important;
            font-weight: 700 !important;
            letter-spacing: 1px !important;
            text-transform: uppercase !important;
            opacity: 0.55;
        }

        [data-testid="stMetricValue"] > div {
            font-size: 28px !important;
            font-weight: 800 !important;
            letter-spacing: -1px !important;
        }

        [data-testid="stMetricDelta"] > div {
            font-size: 12px !important;
        }

        /* ── Health rows ────────────────────────────────────── */
        .health-row {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 0;
            border-bottom: 1px solid rgba(128,128,128,0.12);
            font-size: 13px;
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

        .health-field { font-weight: 600; flex: 1; }
        .health-val   { opacity: 0.55; font-size: 12px; }

        /* ── Empty state ────────────────────────────────────── */
        .empty-state {
            text-align: center;
            padding: 60px 40px;
            opacity: 0.6;
        }

        .empty-icon {
            font-size: 36px;
            margin-bottom: 12px;
        }

        .empty-title {
            font-size: 17px;
            font-weight: 700;
            margin-bottom: 6px;
        }

        .empty-body {
            font-size: 14px;
            opacity: 0.75;
            max-width: 360px;
            margin: 0 auto;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

def render_hero(df: pd.DataFrame) -> None:
    source_count = df["source"].nunique() if "source" in df.columns else 0
    tags = ["SQLite", "Pandas", "Deduplication", f"{source_count} source{'s' if source_count != 1 else ''}", "ETL pipeline"]
    tags_html = "".join(f'<span class="hero-tag">{t}</span>' for t in tags)
    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-eyebrow">
                <span class="hero-dot"></span>
                Live pipeline
            </div>
            <div class="hero-title">Job Market <span class="accent">Intelligence</span></div>
            <div class="hero-sub">
                End-to-end ETL: scraping, cleaning, deduplication, SQLite storage, and analytics.
            </div>
            <div class="hero-tags">{tags_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.markdown("## ◌ JobOS")
    st.sidebar.caption("Filters apply across all tabs.")
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

    if "remote_flag" in filtered.columns:
        remote_only = st.sidebar.checkbox("Remote only")
        if remote_only:
            filtered = filtered[filtered["remote_flag"] == True]  # noqa: E712

    query = st.sidebar.text_input("Search title or company", placeholder="e.g. engineer, Google")
    if query:
        q = query.lower()
        filtered = filtered[
            filtered["title"].fillna("").str.lower().str.contains(q)
            | filtered["company"].fillna("").str.lower().str.contains(q)
        ]

    st.sidebar.divider()
    shown = len(filtered)
    total = len(df)
    pct = f"{shown / total * 100:.0f}%" if total else "—"
    st.sidebar.caption(f"Showing **{shown:,}** of **{total:,}** records ({pct})")

    return filtered


def section_header(title: str, subtitle: str = "") -> None:
    sub_html = f'<span class="sec-count">{subtitle}</span>' if subtitle else ""
    st.markdown(
        f'<div class="sec-header"><span class="sec-title">{title}</span>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def empty_chart(message: str = "No data available") -> None:
    st.markdown(
        f"""
        <div class="empty-state">
            <div class="empty-icon">◌</div>
            <div class="empty-title">{message}</div>
            <div class="empty-body">Run the pipeline to populate this chart.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(df: pd.DataFrame) -> None:
    total = len(df)
    active = int((df["status"] == "active").sum()) if "status" in df.columns else 0
    incomplete = int((df["status"] == "incomplete").sum()) if "status" in df.columns else 0
    remote = int(df["remote_flag"].sum()) if "remote_flag" in df.columns else 0
    companies = df["company"].nunique() if "company" in df.columns else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total jobs", f"{total:,}", help="After cleaning and deduplication")
    c2.metric("Active", f"{active:,}", help="Ready for outreach or analysis")
    c3.metric("Incomplete", f"{incomplete:,}",
              delta=f"-{incomplete}" if incomplete else None,
              delta_color="inverse",
              help="Missing one or more critical fields")
    c4.metric("Remote", f"{remote:,}", help="Remote-friendly postings")
    c5.metric("Companies", f"{companies:,}", help="Unique hiring companies")


def render_overview_charts(df: pd.DataFrame) -> None:
    try:
        import plotly.express as px
        _plotly = True
    except ImportError:
        _plotly = False

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            section_header("Top job titles", "by frequency")
            if not df.empty and "title" in df.columns:
                data = df["title"].fillna("Unknown").value_counts().head(10).reset_index()
                data.columns = ["Title", "Count"]
                if _plotly:
                    import plotly.express as px
                    fig = px.bar(
                        data.sort_values("Count"), x="Count", y="Title",
                        orientation="h",
                        color_discrete_sequence=["#10B981"],
                    )
                    fig.update_layout(
                        margin=dict(l=0, r=0, t=8, b=0),
                        height=280,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        showlegend=False,
                        xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)", title=""),
                        yaxis=dict(showgrid=False, title=""),
                        font=dict(family="Inter, sans-serif", size=12),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.bar_chart(data.set_index("Title")["Count"])
            else:
                empty_chart("No title data")

    with col2:
        with st.container(border=True):
            section_header("Top hiring companies", "by postings")
            if not df.empty and "company" in df.columns:
                data = df["company"].fillna("Unknown").value_counts().head(10).reset_index()
                data.columns = ["Company", "Postings"]
                if _plotly:
                    import plotly.express as px
                    fig = px.bar(
                        data.sort_values("Postings"), x="Postings", y="Company",
                        orientation="h",
                        color_discrete_sequence=["#6366F1"],
                    )
                    fig.update_layout(
                        margin=dict(l=0, r=0, t=8, b=0),
                        height=280,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        showlegend=False,
                        xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)", title=""),
                        yaxis=dict(showgrid=False, title=""),
                        font=dict(family="Inter, sans-serif", size=12),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.bar_chart(data.set_index("Company")["Postings"])
            else:
                empty_chart("No company data")

    col3, col4 = st.columns(2)

    with col3:
        with st.container(border=True):
            section_header("Remote vs on-site")
            if not df.empty and "remote_flag" in df.columns:
                counts = (
                    df["remote_flag"]
                    .map({True: "Remote", False: "On-site / Hybrid"})
                    .value_counts()
                    .reset_index()
                )
                counts.columns = ["Type", "Count"]
                if _plotly:
                    import plotly.express as px
                    fig = px.pie(
                        counts, names="Type", values="Count",
                        color_discrete_sequence=["#10B981", "#94A3B8"],
                        hole=0.52,
                    )
                    fig.update_layout(
                        margin=dict(l=0, r=0, t=8, b=0),
                        height=260,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        legend=dict(orientation="h", yanchor="bottom", y=-0.15),
                        font=dict(family="Inter, sans-serif", size=12),
                    )
                    fig.update_traces(textinfo="percent+label", textposition="outside")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.bar_chart(counts.set_index("Type")["Count"])
            else:
                empty_chart("No remote data")

    with col4:
        with st.container(border=True):
            section_header("New listings over time", "by first-seen date")
            if not df.empty and "first_seen" in df.columns:
                daily = (
                    df.dropna(subset=["first_seen"])
                    .assign(d=lambda x: x["first_seen"].dt.date)
                    .groupby("d")
                    .size()
                    .reset_index(name="Count")
                )
                daily.columns = ["Date", "Count"]
                if _plotly:
                    import plotly.express as px
                    fig = px.area(
                        daily, x="Date", y="Count",
                        color_discrete_sequence=["#10B981"],
                    )
                    fig.update_traces(fillcolor="rgba(16,185,129,0.12)", line_color="#10B981")
                    fig.update_layout(
                        margin=dict(l=0, r=0, t=8, b=0),
                        height=260,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        showlegend=False,
                        xaxis=dict(showgrid=False, title=""),
                        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)", title=""),
                        font=dict(family="Inter, sans-serif", size=12),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.line_chart(daily.set_index("Date")["Count"])
            else:
                empty_chart("No date data")


def render_jobs_table(df: pd.DataFrame) -> None:
    section_header("Clean job records", f"{len(df):,} results")

    display_cols = [
        "title", "company", "seniority_level", "region", "remote_flag",
        "salary_min", "salary_max", "salary_currency", "date_posted", "source", "status", "url",
    ]
    available = [c for c in display_cols if c in df.columns]

    # Column config for better display
    col_config = {
        "title":           st.column_config.TextColumn("Title", width="medium"),
        "company":         st.column_config.TextColumn("Company", width="medium"),
        "seniority_level": st.column_config.TextColumn("Seniority", width="small"),
        "remote_flag":     st.column_config.CheckboxColumn("Remote"),
        "salary_min":      st.column_config.NumberColumn("Min salary", format="%.0f"),
        "salary_max":      st.column_config.NumberColumn("Max salary", format="%.0f"),
        "salary_currency": st.column_config.TextColumn("Currency", width="small"),
        "date_posted":     st.column_config.DateColumn("Posted"),
        "url":             st.column_config.LinkColumn("Link", display_text="Open ↗"),
    }

    st.dataframe(
        df[available],
        use_container_width=True,
        hide_index=True,
        column_config={k: v for k, v in col_config.items() if k in available},
    )

    st.download_button(
        label="⬇ Download filtered CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="filtered_jobs.csv",
        mime="text/csv",
    )


def render_salary_section(df: pd.DataFrame) -> None:
    section_header("Salary breakdown", "by role where data is available")

    if df.empty or "salary_midpoint" not in df.columns:
        empty_chart("No salary data")
        return

    salary_df = df.dropna(subset=["salary_midpoint"]).copy()
    if salary_df.empty:
        st.info("No salary data in the current selection. Try broadening your filters.")
        return

    # Summary coverage callout
    pct = len(salary_df) / len(df) * 100
    st.caption(f"Salary data available for **{len(salary_df):,}** of {len(df):,} records ({pct:.0f}%).")

    summary = (
        salary_df.groupby(["title", "salary_currency"], dropna=False)
        .agg(
            count=("id" if "id" in salary_df.columns else "salary_midpoint", "count"),
            salary_min=("salary_min", "min"),
            salary_median=("salary_midpoint", "median"),
            salary_max=("salary_max", "max"),
        )
        .reset_index()
        .sort_values(["count", "salary_median"], ascending=[False, False])
    )

    # Rename for display
    summary.columns = ["Title", "Currency", "Listings", "Min", "Median", "Max"]

    try:
        import plotly.express as px
        top = summary.head(12)
        fig = px.bar(
            top.sort_values("Median"),
            x="Median", y="Title", orientation="h",
            error_x=top.sort_values("Median")["Max"] - top.sort_values("Median")["Median"],
            color_discrete_sequence=["#6366F1"],
            labels={"Median": "Median salary", "Title": ""},
        )
        fig.update_layout(
            margin=dict(l=0, r=0, t=8, b=0),
            height=max(240, len(top) * 28),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)"),
            yaxis=dict(showgrid=False),
            font=dict(family="Inter, sans-serif", size=12),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Error bars extend to the max salary reported for that role.")
    except ImportError:
        pass

    st.dataframe(summary, use_container_width=True, hide_index=True)


def health_row_html(label: str, value: str, status: str) -> str:
    dot = {"green": "dot-green", "amber": "dot-amber", "red": "dot-red"}.get(status, "dot-green")
    return (
        f'<div class="health-row">'
        f'<span class="health-dot {dot}"></span>'
        f'<span class="health-field">{label}</span>'
        f'<span class="health-val">{value}</span>'
        f'</div>'
    )


def render_data_quality(df: pd.DataFrame) -> None:
    """Renamed from Pipeline Health — more descriptive."""
    total = len(df)
    if total == 0:
        st.info("No records available. Run the ETL pipeline first (`python main.py`).")
        return

    incomplete = int((df["status"] == "incomplete").sum()) if "status" in df.columns else 0
    completeness = (total - incomplete) / total * 100
    source_count = df["source"].nunique() if "source" in df.columns else 0

    # Top-line metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Records in pipeline", f"{total:,}")
    c2.metric("Complete records", f"{completeness:.1f}%",
              delta="above target" if completeness > 80 else "below 80% target",
              delta_color="normal" if completeness > 80 else "inverse")
    c3.metric("Incomplete", f"{incomplete:,}",
              delta=f"-{incomplete}" if incomplete else None,
              delta_color="inverse")
    c4.metric("Active sources", f"{source_count}")

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    missing_title = int(df["title"].isna().sum()) if "title" in df.columns else 0
    missing_company = int(df["company"].isna().sum()) if "company" in df.columns else 0
    missing_url = int(df["url"].isna().sum()) if "url" in df.columns else 0
    missing_salary = int(df[["salary_min", "salary_max"]].isna().all(axis=1).sum()) if (
        "salary_min" in df.columns and "salary_max" in df.columns
    ) else total

    def dot_status(missing: int) -> str:
        if missing == 0:
            return "green"
        elif missing / total < 0.1:
            return "amber"
        return "red"

    with col1:
        with st.container(border=True):
            section_header("Field completeness")
            rows = (
                health_row_html("Title", f"{missing_title:,} missing", dot_status(missing_title))
                + health_row_html("Company", f"{missing_company:,} missing", dot_status(missing_company))
                + health_row_html("URL", f"{missing_url:,} missing", dot_status(missing_url))
                + health_row_html("Salary", f"{missing_salary:,} missing",
                                  "amber" if missing_salary / total < 0.5 else "red")
            )
            st.markdown(rows, unsafe_allow_html=True)

    with col2:
        with st.container(border=True):
            section_header("Records per source")
            if "source" in df.columns:
                data = df["source"].fillna("Unknown").value_counts().reset_index()
                data.columns = ["Source", "Count"]
                try:
                    import plotly.express as px
                    fig = px.bar(data, x="Source", y="Count", color_discrete_sequence=["#10B981"])
                    fig.update_layout(
                        margin=dict(l=0, r=0, t=8, b=0),
                        height=200,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        showlegend=False,
                        xaxis=dict(showgrid=False, title=""),
                        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)", title=""),
                        font=dict(family="Inter, sans-serif", size=12),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    st.bar_chart(data.set_index("Source")["Count"])
            else:
                empty_chart("No source data")

    st.markdown("<br>", unsafe_allow_html=True)
    section_header("Recent records", "last 20 by pipeline date")

    recent_cols = ["title", "company", "source", "status", "first_seen", "last_seen"]
    available = [c for c in recent_cols if c in df.columns]
    recent = (
        df.sort_values("last_seen", ascending=False).head(20)
        if "last_seen" in df.columns
        else df.head(20)
    )
    st.dataframe(recent[available], use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    inject_css()

    with st.spinner("Loading job data…"):
        df = load_data()

    if not df.empty:
        filtered_df = render_sidebar_filters(df)
    else:
        filtered_df = df

    render_hero(filtered_df if not filtered_df.empty else df)

    if df.empty:
        st.warning(
            "**No job data found.** Run `python main.py` to populate the database, "
            "or include `output/jobs_clean.csv` in the repository before deploying.",
            icon="⚠️",
        )
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-icon">◌</div>
                <div class="empty-title">Pipeline hasn't run yet</div>
                <div class="empty-body">
                    Once jobs.db or jobs_clean.csv is present, this dashboard will populate automatically.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    tab_overview, tab_jobs, tab_salary, tab_quality = st.tabs(
        ["Overview", "Jobs explorer", "Salary analysis", "Data quality"]
    )

    with tab_overview:
        st.markdown("<br>", unsafe_allow_html=True)
        render_kpis(filtered_df)
        st.markdown("<br>", unsafe_allow_html=True)
        render_overview_charts(filtered_df)

    with tab_jobs:
        render_jobs_table(filtered_df)

    with tab_salary:
        render_salary_section(filtered_df)

    with tab_quality:
        render_data_quality(filtered_df)


if __name__ == "__main__":
    main()