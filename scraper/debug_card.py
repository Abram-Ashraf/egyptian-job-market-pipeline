"""
Run this to dump the raw page structure so we can find the real card selectors.
    python debug_card.py
"""
import requests
from bs4 import BeautifulSoup

# No Accept-Encoding — let requests handle decompression automatically
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

resp = requests.get("https://wuzzuf.net/a/Data-Analyst-Jobs-in-Egypt", headers=HEADERS, timeout=15)
print(f"Status: {resp.status_code} | Page length: {len(resp.text)} chars")
print(f"Content-Encoding: {resp.headers.get('Content-Encoding', 'none')}\n")

soup = BeautifulSoup(resp.text, "html.parser")

# 1. Heading tags
print("=== HEADING TAGS ===")
for tag in ["h1", "h2", "h3", "h4"]:
    els = soup.find_all(tag)
    print(f"  <{tag}>: {len(els)} found")
    for el in els[:3]:
        print(f"    {repr(el.get_text(strip=True)[:80])}")

# 2. Job links
print("\n=== LINKS TO /jobs/p/ ===")
job_links = soup.find_all("a", href=lambda h: h and "/jobs/p/" in h)
print(f"  Found {len(job_links)}")
for a in job_links[:5]:
    print(f"  {repr(a.get_text(strip=True)[:60]):65s}  {a['href'][:80]}")

# 3. Company links
print("\n=== LINKS TO /jobs/careers/ ===")
company_links = soup.find_all("a", href=lambda h: h and "/jobs/careers/" in h)
print(f"  Found {len(company_links)}")
for a in company_links[:5]:
    print(f"  {repr(a.get_text(strip=True)[:60]):65s}  {a['href'][:80]}")

# 4. Parent chain of first job link
if job_links:
    print("\n=== PARENT CHAIN OF FIRST JOB LINK ===")
    el = job_links[0]
    for i in range(7):
        print(f"  [{i}] <{el.name}> class={el.get('class')} id={el.get('id')}")
        if el.parent:
            el = el.parent
        else:
            break

    print("\n=== FIRST CARD HTML (grandparent, 3000 chars) ===")
    container = job_links[0]
    for _ in range(4):
        if container.parent:
            container = container.parent
    print(container.prettify()[:3000])

    print("\n=== ALL STRINGS IN FIRST CARD ===")
    container = job_links[0]
    for _ in range(4):
        if container.parent:
            container = container.parent
    for i, s in enumerate(container.strings):
        t = s.strip()
        if t:
            print(f"  [{i:02d}] {repr(t)}")

else:
    print("\n=== NO JOB LINKS — first 2000 chars of readable text ===")
    print(soup.get_text()[:2000])