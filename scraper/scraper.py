"""
Wuzzuf Job Market Scraper
=========================
Scrapes job listings from wuzzuf.net using the /a/ URL pattern.
Outputs a clean CSV ready for SSIS ingestion.

Usage:
    python scraper.py                                          # default keywords
    python scraper.py --keywords "data analyst" "power bi"    # custom keywords
    python scraper.py --keywords "data engineer" --pages 10   # more pages
"""

import requests
from bs4 import BeautifulSoup, Comment
import pandas as pd
import time
import random
import logging
import argparse
import re
from datetime import datetime
from pathlib import Path

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraper.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_URL     = "https://wuzzuf.net"
LISTING_URL  = "https://wuzzuf.net/a/{slug}-Jobs-in-Egypt"

# No Accept-Encoding — let requests decompress automatically
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

DEFAULT_KEYWORDS = [
    "Data-Analyst",
    "Data-Engineer",
    "Business-Intelligence",
    "Power-BI",
    "SQL-Developer",
    "Data-Scientist",
    "ETL-Developer",
    "Reporting-Analyst",
]

EXPERIENCE_LEVELS = {
    "entry level", "experienced", "manager", "senior", "junior",
    "intern", "internship", "graduate", "fresh grad"
}
JOB_TYPES = {
    "full time", "part time", "freelance", "contract",
    "on-site", "hybrid", "remote", "work from home"
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def polite_sleep(min_s=1.5, max_s=3.5):
    time.sleep(random.uniform(min_s, max_s))


def clean(el) -> str:
    if el is None:
        return ""
    if hasattr(el, "get_text"):
        # Strip HTML comments (<!-- -->) that Wuzzuf injects between city parts
        for c in el.find_all(string=lambda t: isinstance(t, Comment)):
            c.extract()
        return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
    return re.sub(r"\s+", " ", str(el)).strip()


def parse_salary(raw: str) -> tuple[str, str]:
    if not raw or "confidential" in raw.lower():
        return ("", "")
    cleaned = re.sub(r"[A-Za-z,]", "", raw).strip()
    m = re.search(r"([\d.]+)\s*[–—\-]+\s*([\d.]+)", cleaned)
    if m:
        return (m.group(1).replace(".", ""), m.group(2).replace(".", ""))
    s = re.search(r"[\d.]+", cleaned)
    if s:
        v = s.group().replace(".", "")
        return (v, v)
    return ("", "")


def keyword_to_slug(keyword: str) -> str:
    return "-".join(w.capitalize() for w in keyword.strip().split())

# ── Page fetcher ──────────────────────────────────────────────────────────────

def fetch_page(slug: str, start: int, session: requests.Session):
    url    = LISTING_URL.format(slug=slug)
    params = {"start": start} if start > 0 else {}
    try:
        r = session.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except requests.exceptions.HTTPError as e:
        log.warning(f"HTTP {e.response.status_code} — slug={slug} start={start}")
        if e.response.status_code == 429:
            log.warning("Rate limited — sleeping 60s")
            time.sleep(60)
    except requests.exceptions.RequestException as e:
        log.error(f"Request error: {e}")
    return None

# ── Card finder ───────────────────────────────────────────────────────────────

def find_cards(soup: BeautifulSoup) -> list:
    """
    Find job card containers using structural logic, not CSS class names.
    Strategy: locate every <a href="/jobs/p/..."> (job title link),
    then walk up the DOM until we reach a container that also holds
    a company link (/jobs/careers/). That container = one card.
    """
    cards = []
    seen  = set()

    for title_link in soup.find_all("a", href=re.compile(r"^/jobs/p/")):
        container = title_link.parent  # start at <h2>
        for _ in range(6):
            if container is None:
                break
            if container.find("a", href=re.compile(r"/jobs/careers/")):
                break
            container = container.parent

        if container is None or id(container) in seen:
            continue
        seen.add(id(container))
        cards.append(container)

    return cards

# ── Card parser ───────────────────────────────────────────────────────────────

def parse_card(card, slug: str, scraped_at: str) -> dict | None:
    """
    Parse one job card using structural position, not CSS class names.

    Confirmed card structure (from live HTML inspection):
      container div
        ├── <a href="/jobs/careers/..."><img></a>        ← logo (skip)
        ├── <a href="/jobs/careers/...">Company -</a>    ← company name
        ├── <span>City, Country</span>                   ← location
        ├── <div>N days ago</div>                        ← post date
        ├── <h2><a href="/jobs/p/...">Title</a></h2>     ← job title
        └── tags: Full Time, Hybrid, Entry Level, skills...
    """
    try:
        # ── Title ──
        title_link = card.find("a", href=re.compile(r"^/jobs/p/"))
        if not title_link:
            return None
        title   = clean(title_link)
        job_url = BASE_URL + title_link["href"]

        # ── Company ──
        # The company <a> links to /jobs/careers/ AND contains visible text (not just an img)
        company = ""
        for a in card.find_all("a", href=re.compile(r"/jobs/careers/")):
            text = clean(a)
            if text:                       # skip the logo-only link
                company = text.rstrip(" -–").strip()
                break

        # ── Location ──
        # Sits in a <span> that is a sibling of the company <a>, inside the same wrapper div.
        # Contains city parts separated by <!-- --> comments e.g. "Nasr City, Cairo, Egypt"
        location = ""
        company_el = card.find("a", href=re.compile(r"/jobs/careers/"), string=True)
        if not company_el:
            # fallback: first careers link with text content
            for a in card.find_all("a", href=re.compile(r"/jobs/careers/")):
                if clean(a):
                    company_el = a
                    break
        if company_el:
            span = company_el.find_next_sibling("span")
            if span:
                location = clean(span)

        # ── Post date ──
        # A short <div> or <span> whose text matches time patterns
        post_date = ""
        for el in card.find_all(["div", "span"]):
            t = clean(el)
            if re.search(r"\d+\s+(day|week|month|hour)s?\s+ago|yesterday|today", t, re.I):
                post_date = t
                break

        # ── Classify all tag links ──
        # Every tag is an <a href="/a/..."> or <a href="https://wuzzuf.net/a/...">
        job_types  = []
        experience = []
        skills     = []

        for a in card.find_all("a", href=re.compile(r"/a/")):
            label = clean(a).lstrip("·").strip()
            if not label:
                continue
            low = label.lower()
            if any(jt in low for jt in JOB_TYPES):
                job_types.append(label)
            elif any(el in low for el in EXPERIENCE_LEVELS):
                experience.append(label)
            else:
                skills.append(label)

        # ── Years of experience (plain text node like "0 - 3 Yrs of Exp") ──
        years_exp = ""
        for s in card.strings:
            t = s.strip()
            if re.search(r"\d.*yrs?\s+of\s+exp", t, re.I):
                years_exp = t
                break

        # ── Salary ──
        salary_raw = ""
        for s in card.strings:
            t = s.strip()
            if "egp" in t.lower() or re.search(r"\d[\d,]+\s*[-–]\s*\d[\d,]+", t):
                salary_raw = t
                break
        salary_min, salary_max = parse_salary(salary_raw)

        return {
            "job_title":        title,
            "company_name":     company,
            "location":         location,
            "job_type":         " | ".join(job_types),
            "experience_level": " | ".join(experience),
            "years_experience": years_exp,
            "skills":           " | ".join(skills),
            "salary_raw":       salary_raw,
            "salary_min_egp":   salary_min,
            "salary_max_egp":   salary_max,
            "post_date_raw":    post_date,
            "job_url":          job_url,
            "search_keyword":   slug.replace("-", " "),
            "scraped_at":       scraped_at,
        }

    except Exception as e:
        log.debug(f"Card parse error: {e}")
        return None

# ── Per-keyword scraper ───────────────────────────────────────────────────────

def scrape_keyword(slug: str, max_pages: int, session: requests.Session) -> list[dict]:
    jobs       = []
    scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info(f"▶  Scraping '{slug}' — up to {max_pages} page(s)")

    for page in range(max_pages):
        soup = fetch_page(slug, start=page * 15, session=session)
        if not soup:
            break

        cards = find_cards(soup)
        if not cards:
            log.info(f"  Page {page + 1}: no cards found — stopping")
            break

        page_jobs = [j for c in cards if (j := parse_card(c, slug, scraped_at))]
        log.info(f"  Page {page + 1}: {len(page_jobs)} jobs")
        jobs.extend(page_jobs)

        if len(page_jobs) < 5:
            log.info("  Looks like the last page — stopping early")
            break

        polite_sleep()

    log.info(f"  '{slug}' total: {len(jobs)} jobs\n")
    return jobs

# ── Main run ──────────────────────────────────────────────────────────────────

def run(keywords: list[str], max_pages: int, output_path: str) -> pd.DataFrame:
    all_jobs: list[dict] = []
    seen_urls: set[str]  = set()

    slugs = [keyword_to_slug(kw) if " " in kw else kw for kw in keywords]

    with requests.Session() as session:
        for slug in slugs:
            for job in scrape_keyword(slug, max_pages, session):
                url = job.get("job_url", "")
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                all_jobs.append(job)
            polite_sleep(2, 4)

    df = pd.DataFrame(all_jobs)
    if df.empty:
        log.warning("No jobs scraped.")
        return df

    before = len(df)
    df.drop_duplicates(subset=["job_url"], keep="first", inplace=True)
    df.reset_index(drop=True, inplace=True)
    log.info(f"Dedup: {before} → {len(df)} rows")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    log.info(f"✓  Saved {len(df)} jobs → {output_path}")

    print("\n── Summary ──────────────────────────────────")
    print(f"Total unique jobs  : {len(df)}")
    print(f"Keywords scraped   : {', '.join(slugs)}")
    print(f"Output             : {output_path}")
    if df["location"].str.strip().any():
        print(f"\nTop locations:\n{df['location'].value_counts().head(5).to_string()}")
    if df["company_name"].str.strip().any():
        print(f"\nTop companies:\n{df['company_name'].value_counts().head(5).to_string()}")
    if df["skills"].str.strip().any():
        # Flatten all skills to find most common
        all_skills = df["skills"].dropna().str.split(" | ").explode()
        all_skills = all_skills[all_skills.str.strip() != ""]
        print(f"\nTop skills:\n{all_skills.value_counts().head(10).to_string()}")
    print("─────────────────────────────────────────────\n")

    return df

# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wuzzuf job market scraper")
    parser.add_argument("--keywords", nargs="+", default=DEFAULT_KEYWORDS)
    parser.add_argument("--pages",   type=int, default=5)
    parser.add_argument(
        "--output",
        default=f"output/wuzzuf_{datetime.now().strftime('%Y%m%d')}.csv"
    )
    args = parser.parse_args()
    run(keywords=args.keywords, max_pages=args.pages, output_path=args.output)