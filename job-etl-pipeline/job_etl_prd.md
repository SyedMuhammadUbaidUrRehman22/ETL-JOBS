# PRD — Automated Job Market ETL Pipeline

**Project Type:** Portfolio  
**Stack:** Python · BeautifulSoup · SQLite · Pandas  
**Goal:** Demonstrate end-to-end ETL competency — scraping, cleaning, deduplication, storage, and reporting

---

## 1. Problem Statement

Job seekers and recruiters need aggregated, clean job market data from multiple sources. Raw job boards are noisy, duplicate-heavy, and unstructured. This pipeline extracts postings from public job sites, cleans and normalises the data, removes duplicates, stores it in a queryable database, and generates analytical reports — fully automated.

---

## 2. Objectives

- Scrape job postings from at least 2 public sources
- Normalise inconsistent fields (titles, salaries, locations, dates)
- Deduplicate across sources using fingerprinting
- Store clean records in SQLite with full history tracking
- Generate summary reports in CSV and HTML
- Log every pipeline run with row-level outcomes

---

## 3. Scope

### In Scope
- Public job board scraping (no login required)
- Field normalisation and cleaning
- Duplicate detection and resolution
- SQLite storage with schema versioning
- Pandas-based reporting and export
- CLI runner with configurable parameters

### Out of Scope
- Authenticated scraping / paid APIs
- Real-time / streaming ingestion
- Frontend dashboard
- Cloud deployment (local-first for portfolio)

---

## 4. Functional Requirements

### 4.1 Extract
| ID | Requirement |
|----|-------------|
| E1 | Scrape job postings from at least 2 public sources (e.g. RemoteOK, HN Who's Hiring, Indeed public) |
| E2 | Capture: title, company, location, salary (if available), date posted, job URL, source, description snippet |
| E3 | Support configurable keyword and location filters |
| E4 | Handle pagination up to a configurable page limit |
| E5 | Respect robots.txt and add request delays (1–3s) |
| E6 | Retry failed requests up to 3 times with exponential backoff |

### 4.2 Transform
| ID | Requirement |
|----|-------------|
| T1 | Normalise job titles: strip seniority noise ("Sr.", "Lead", "III") into structured `seniority_level` field |
| T2 | Standardise location to `city`, `state/country`, `remote_flag` |
| T3 | Parse salary ranges into `salary_min`, `salary_max`, `salary_currency` (handle "$80k–$120k", "£50,000 PA", etc.) |
| T4 | Normalise date posted to ISO 8601 (`YYYY-MM-DD`) |
| T5 | Strip HTML tags and excess whitespace from description fields |
| T6 | Generate a dedup fingerprint: SHA-256 hash of `(normalised_title + company + location)` |
| T7 | Flag records missing critical fields (title, company, URL) as `status = 'incomplete'` |

### 4.3 Load
| ID | Requirement |
|----|-------------|
| L1 | Insert new records into SQLite `jobs` table |
| L2 | Skip records whose fingerprint already exists (`status = 'duplicate'`) |
| L3 | Track `first_seen` and `last_seen` timestamps per record |
| L4 | Maintain a `pipeline_runs` table logging run metadata (start time, rows extracted/loaded/skipped/failed) |
| L5 | Export clean data to `output/jobs_clean.csv` after every run |

### 4.4 Report
| ID | Requirement |
|----|-------------|
| R1 | Top 10 job titles by frequency |
| R2 | Top hiring companies |
| R3 | Salary distribution summary (min, median, max, by role) |
| R4 | Remote vs on-site vs hybrid breakdown |
| R5 | New postings per day (last 30 days) |
| R6 | Export reports as `output/report_YYYYMMDD.html` and `.csv` |

---

## 5. Non-Functional Requirements

- Pipeline must complete a full run (2 sources, 100 listings) in under 5 minutes
- SQLite DB must not exceed 500MB for 100k records
- All errors logged to `logs/pipeline.log` — no silent failures
- Code structured as importable modules, not a single script

---

## 6. Database Schema

```sql
-- Core jobs table
CREATE TABLE jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint     TEXT UNIQUE NOT NULL,
    title           TEXT,
    seniority_level TEXT,
    company         TEXT,
    city            TEXT,
    region          TEXT,
    remote_flag     BOOLEAN,
    salary_min      INTEGER,
    salary_max      INTEGER,
    salary_currency TEXT,
    date_posted     DATE,
    source          TEXT,
    url             TEXT,
    description     TEXT,
    status          TEXT DEFAULT 'active',  -- active | duplicate | incomplete
    first_seen      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Run audit log
CREATE TABLE pipeline_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source          TEXT,
    rows_extracted  INTEGER,
    rows_loaded     INTEGER,
    rows_skipped    INTEGER,
    rows_failed     INTEGER,
    duration_secs   REAL
);
```

---

## 7. Project Structure

```
job-etl-pipeline/
│
├── main.py                  # CLI entry point
├── config.yaml              # Keywords, sources, limits, delays
│
├── etl/
│   ├── __init__.py
│   ├── extract/
│   │   ├── base_scraper.py  # Abstract scraper class
│   │   ├── remoteok.py      # Source-specific scraper
│   │   └── hn_hiring.py     # Source-specific scraper
│   ├── transform/
│   │   ├── cleaner.py       # Field normalisation
│   │   ├── deduper.py       # Fingerprint generation + dedup logic
│   │   └── validator.py     # Required field checks
│   └── load/
│       ├── db.py            # SQLite connection + schema init
│       └── loader.py        # Insert / upsert logic
│
├── reports/
│   └── generator.py         # Pandas report generation
│
├── output/                  # Generated CSVs and HTML reports
├── logs/                    # Pipeline run logs
├── tests/                   # Unit tests per module
└── requirements.txt
```

---

## 8. Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PIPELINE RUN                                │
└─────────────────────────────────────────────────────────────────────┘

  CONFIG LOAD
  └── Read config.yaml (keywords, sources, page limits, delays)

         │
         ▼

  EXTRACT (per source)
  ├── Send HTTP request with headers + delay
  ├── Parse HTML with BeautifulSoup
  ├── Extract raw fields (title, company, location, salary, URL, date)
  ├── On failure: retry × 3, then log and skip
  └── Yield raw record dicts to transform stage

         │
         ▼

  TRANSFORM (per record)
  ├── Normalise title → clean_title + seniority_level
  ├── Normalise location → city, region, remote_flag
  ├── Parse salary → salary_min, salary_max, salary_currency
  ├── Parse date → ISO 8601
  ├── Strip HTML from description
  ├── Generate SHA-256 fingerprint
  └── Validate required fields → flag incomplete records

         │
         ▼

  LOAD (per record)
  ├── Check fingerprint against DB
  │   ├── EXISTS → mark duplicate, update last_seen, skip insert
  │   └── NEW    → insert full record, status = active
  ├── Incomplete records → insert with status = incomplete
  └── Write run stats to pipeline_runs table

         │
         ▼

  EXPORT
  ├── Write active + incomplete records to output/jobs_clean.csv
  └── Log run summary to logs/pipeline.log

         │
         ▼

  REPORT GENERATION
  ├── Load clean data via Pandas
  ├── Compute: top titles, top companies, salary stats,
  │           remote breakdown, daily new listings
  ├── Export output/report_YYYYMMDD.csv
  └── Export output/report_YYYYMMDD.html
```

---

## 9. Error Handling Strategy

| Scenario | Behaviour |
|----------|-----------|
| HTTP timeout / 4xx / 5xx | Retry ×3 with backoff, then log as `failed`, continue |
| Missing required field | Insert with `status = 'incomplete'`, log warning |
| Duplicate fingerprint | Update `last_seen`, log as `skipped` |
| Malformed salary string | Set salary fields to NULL, log warning |
| DB write failure | Rollback transaction, log error, abort run |
| Source structure changed | Raise `ScraperError`, log critical, alert in summary |

---

## 10. CLI Usage

```bash
# Run full pipeline (all sources, all keywords from config)
python main.py

# Run single source
python main.py --source remoteok

# Custom keyword + location filter
python main.py --keyword "data engineer" --location "remote"

# Generate report only (no scrape)
python main.py --report-only

# Limit pages per source (useful for testing)
python main.py --max-pages 2
```

---

## 11. Deliverables

| Deliverable | Description |
|-------------|-------------|
| `etl/` module | Fully importable, testable ETL package |
| `jobs.db` | SQLite database with seeded sample data |
| `output/jobs_clean.csv` | Sample clean export |
| `output/report_sample.html` | Sample HTML report |
| `tests/` | Unit tests for cleaner, deduper, validator |
| `README.md` | Setup guide, architecture diagram, sample output |

---

## 12. Portfolio Signal

This project demonstrates:

- **ETL architecture** — clean separation of extract, transform, load concerns
- **Web scraping** — BeautifulSoup, request handling, rate limiting, retries
- **Data cleaning** — regex, normalisation, handling real-world messy data
- **Deduplication** — fingerprint-based across multiple sources
- **Database design** — schema with audit logging, not just a flat CSV dump
- **Pandas reporting** — aggregation, groupby, export
- **Code quality** — modular structure, error handling, logging, CLI interface
