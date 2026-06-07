# Egyptian Job Market Analytics Pipeline

An end-to-end data engineering project that scrapes, transforms, and visualises job market data from Egypt's largest job board — [Wuzzuf.net](https://wuzzuf.net).

## Architecture

```
Wuzzuf.net
    │  Python scraper (BeautifulSoup)
    ▼
scraper/output/*.csv        ← raw scraped data
    │  SSIS ETL packages
    ▼
SSMS Data Warehouse          ← star schema
    │  Power BI DirectQuery
    ▼
Power BI Dashboard           ← insights & trends
```

## Stack

| Layer | Tool |
|---|---|
| Data collection | Python, BeautifulSoup, APScheduler |
| Storage | SQL Server (SSMS) |
| ETL | SSIS |
| Visualisation | Power BI, DAX |

## Project Phases

| Phase | Status | Description |
|---|---|---|
| 1 — Scraper | ✅ Done | Python scraper targeting Wuzzuf.net, weekly scheduler |
| 2 — DWH Design | 🔄 In progress | Star schema: fact + 5 dimensions |
| 3 — SSIS ETL | ⏳ Upcoming | Load, clean, transform into warehouse |
| 4 — Power BI | ⏳ Upcoming | Dashboard with skills, salary, trends |

## Quickstart

```bash
# 1. Install dependencies
cd scraper
pip install -r requirements.txt

# 2. Run a one-off scrape (all default keywords, 5 pages each)
python scraper.py

# 3. Run on a weekly schedule (every Sunday 08:00 Cairo time)
python scheduler.py
```

Output CSV lands in `scraper/output/wuzzuf_YYYYMMDD.csv`, encoded `utf-8-sig` for SSIS compatibility.

## Dashboard Preview

*Screenshots will be added in Phase 4.*

## Key Insights (updated weekly)

*Will be populated once enough data is collected.*

## Author

Abram Ashraf — Data Engineer & Analyst
[LinkedIn](https://linkedin.com/in/) · [GitHub](https://github.com/)
