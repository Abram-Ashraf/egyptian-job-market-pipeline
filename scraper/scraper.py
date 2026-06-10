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
    "intern", "internship", "graduate", "fresh grad", "senior management"
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
    Find individual job card containers.
    Each card is a div with class containing 'e1v1l3u10' — this is the
    stable Emotion.js instance class that identifies a single card.
    Fallback: walk up from each job title link until we find a container
    that has ONLY ONE /jobs/p/ link inside it.
    """
    cards = []
    seen  = set()

    # Primary strategy: find divs with the stable instance class e1v1l3u10
    # This class identifies a single card component instance
    for div in soup.find_all("div", class_=re.compile(r"e1v1l3u10")):
        job_links = div.find_all("a", href=re.compile(r"^/jobs/p/"))
        if len(job_links) == 1 and id(div) not in seen:
            seen.add(id(div))
            cards.append(div)

    if cards:
        return cards

    # Fallback: walk up from each title link, stop when container has exactly 1 job link
    for title_link in soup.find_all("a", href=re.compile(r"^/jobs/p/")):
        container = title_link.parent
        for _ in range(8):
            if container is None:
                break
            job_links_in_container = container.find_all("a", href=re.compile(r"^/jobs/p/"))
            company_link = container.find("a", href=re.compile(r"/jobs/careers/"))
            if len(job_links_in_container) == 1 and company_link:
                break
            container = container.parent

        if container is None or id(container) in seen:
            continue
        seen.add(id(container))
        cards.append(container)

    return cards

# ── Card parser ───────────────────────────────────────────────────────────────

def parse_card(card, slug: str, scraped_at: str) -> dict | None:
    try:
        # ── Title ──
        title_link = card.find("a", href=re.compile(r"^/jobs/p/"))
        if not title_link:
            return None
        title   = clean(title_link)
        job_url = BASE_URL + title_link["href"]

        # ── Company ──
        company = ""
        for a in card.find_all("a", href=re.compile(r"/jobs/careers/")):
            text = clean(a)
            if text:
                company = text.rstrip(" -–").strip()
                break

        # ── Location ──
        location = ""
        company_el = None
        for a in card.find_all("a", href=re.compile(r"/jobs/careers/")):
            if clean(a):
                company_el = a
                break
        if company_el:
            span = company_el.find_next_sibling("span")
            if span:
                location = clean(span)

        # ── Post date ──
        post_date = ""
        for el in card.find_all(["div", "span"]):
            t = clean(el)
            if re.search(r"\d+\s+(day|week|month|hour)s?\s+ago|yesterday|today", t, re.I):
                post_date = t
                break

        # ── Tags: only from THIS card's tag section ──
        # The tag section is a div that comes AFTER the title/company block
        # and contains only /a/ links. We identify it by finding the div
        # that directly contains the job type / experience / skill links.
        # Key insight: only look at <a> tags that are DIRECT descendants
        # of the card, not nested inside the title or company sections.

        job_types  = []
        experience = []
        skills     = []

        # Find the tags wrapper div — it's the div after css-lptxge (title block)
        # It contains short text links like "Full Time", "On-site", "Entry Level"
        title_block = card.find("div", class_=re.compile(r"css-lptxge"))
        tag_divs = []
        if title_block:
            # Get all sibling divs after the title block
            for sibling in title_block.find_next_siblings("div"):
                tag_divs.append(sibling)
        
        # Search for /a/ tags only within the tag divs (not title/company area)
        search_area = tag_divs if tag_divs else [card]
        
        for area in search_area:
            for a in area.find_all("a", href=re.compile(r"/a/")):
                label = clean(a).lstrip("·").strip()
                if not label or len(label) > 100:  # skip very long labels
                    continue
                low = label.lower()
                if any(jt in low for jt in JOB_TYPES):
                    job_types.append(label)
                elif any(el in low for el in EXPERIENCE_LEVELS):
                    experience.append(label)
                else:
                    skills.append(label)

        # Deduplicate while preserving order
        job_types  = list(dict.fromkeys(job_types))
        experience = list(dict.fromkeys(experience))
        skills     = list(dict.fromkeys(skills))

        # ── Years of experience ──
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