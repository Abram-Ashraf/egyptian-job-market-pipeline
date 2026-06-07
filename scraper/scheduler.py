"""
scheduler.py
============
Runs the Wuzzuf scraper on a weekly schedule using APScheduler.
Run this once and leave it running in the background.

    python scheduler.py
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging
from scraper import run, DEFAULT_KEYWORDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

scheduler = BlockingScheduler(timezone="Africa/Cairo")


def weekly_scrape():
    """Job that runs every week."""
    log.info("⏰ Scheduled scrape starting...")
    output_path = f"output/wuzzuf_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    run(
        keywords=DEFAULT_KEYWORDS,
        max_pages=5,
        output_path=output_path,
    )
    log.info("✓ Scheduled scrape complete.")


# Run every Sunday at 08:00 Cairo time
scheduler.add_job(
    weekly_scrape,
    trigger=CronTrigger(day_of_week="sun", hour=8, minute=0),
    id="wuzzuf_weekly",
    name="Wuzzuf weekly scrape",
    misfire_grace_time=3600,   # If missed, still run within 1 hour
)

if __name__ == "__main__":
    log.info("Scheduler started. Next run: every Sunday at 08:00 Cairo time.")
    log.info("Press Ctrl+C to stop.")
    # Optionally run once immediately on startup:
    # weekly_scrape()
    scheduler.start()
