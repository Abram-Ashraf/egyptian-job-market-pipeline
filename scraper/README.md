# Wuzzuf Job Market Scraper

Part of the **Egyptian Job Market Analytics Pipeline** project.

## What it does

Scrapes job listings from [wuzzuf.net](https://wuzzuf.net) across configurable
search keywords. Outputs a clean CSV file ready for SSIS ingestion.

### Fields collected per job

| Column | Description |
|---|---|
| `job_title` | Job posting title |
| `company_name` | Hiring company |
| `location` | City / area in Egypt |
| `job_type` | Full-time, Part-time, Freelance, etc. |
| `experience_level` | Entry level, Experienced, Senior, etc. |
| `skills` | Pipe-separated required skills |
| `salary_raw` | Raw salary text from the listing |
| `salary_min_egp` | Parsed minimum salary (EGP) |
| `salary_max_egp` | Parsed maximum salary (EGP) |
| `post_date_raw` | Date posted (raw text, e.g. "2 days ago") |
| `job_url` | Direct link to the listing |
| `search_keyword` | Which keyword found this listing |
| `scraped_at` | Timestamp of when it was scraped |

## Setup

```bash
pip install -r requirements.txt
```

## Usage

**Run once (manual):**
```bash
# Default keywords, 5 pages each (~375 jobs)
python scraper.py

# Custom keywords and page depth
python scraper.py --keywords "data analyst" "power bi" "sql" --pages 10

# Custom output path
python scraper.py --output output/my_run.csv
```

**Run on a weekly schedule:**
```bash
python scheduler.py
```
Runs every Sunday at 08:00 Cairo time. Leave the process running.

## Output

Files are saved to `output/wuzzuf_YYYYMMDD.csv` by default.
Encoding is `utf-8-sig` — compatible with Excel and SSIS flat file sources.

## Project architecture

```
Wuzzuf.net
    │
    ▼
scraper.py          ← you are here
    │  CSV (utf-8-sig)
    ▼
SSIS ETL Package    ← Phase 3
    │  Cleaned & transformed
    ▼
SSMS Data Warehouse ← Phase 3
    │  Star schema
    ▼
Power BI Dashboard  ← Phase 4
```

## Notes

- Respects the server with random delays (1.5–3.5s between requests).
- Auto-deduplicates jobs seen across multiple keyword searches.
- If Wuzzuf updates their HTML structure, update the CSS selectors in `parse_job_card()`.
- Salary parsing handles ranges like "5,000–8,000 EGP" and "Confidential".
