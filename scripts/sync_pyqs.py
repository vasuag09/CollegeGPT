"""
PYQ sync orchestrator.
Runs: SVKM portal scraper → Google Drive uploader.
Usage: python scripts/sync_pyqs.py
Exit code: 0 = all success, 1 = any failures.
"""
import logging
import sys
from scripts import pyq_scraper, drive_uploader

logger = logging.getLogger(__name__)


def main() -> int:
    logger.info("=== PYQ Sync started ===")

    try:
        scraper_counts = pyq_scraper.run()
    except RuntimeError as e:
        logger.error("Scraper failed: %s", e)
        scraper_counts = {"downloaded": 0, "skipped": 0, "failed": 1}

    print(
        f"\nScraper:  {scraper_counts['downloaded']} downloaded, "
        f"{scraper_counts['skipped']} skipped, "
        f"{scraper_counts['failed']} failed"
    )

    # Always run uploader — partial sync is better than none
    uploader_counts = drive_uploader.run()
    print(
        f"Uploader: {uploader_counts['uploaded']} uploaded, "
        f"{uploader_counts['skipped']} skipped, "
        f"{uploader_counts['failed']} failed"
    )

    any_failures = scraper_counts["failed"] > 0 or uploader_counts["failed"] > 0
    exit_code = 1 if any_failures else 0
    logger.info("=== PYQ Sync complete (exit %d) ===", exit_code)
    return exit_code


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    sys.exit(main())
