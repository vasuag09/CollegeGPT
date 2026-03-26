"""
PYQ sync orchestrator.
Runs: SVKM portal scraper → Google Drive uploader (concurrent, file-by-file).
Each file is uploaded to Drive and deleted locally immediately after download.
Usage:
  python -m scripts.sync_pyqs                  # all branches
  python -m scripts.sync_pyqs --branch btech-ce
  python -m scripts.sync_pyqs --branch btech-cs
  python -m scripts.sync_pyqs --branch btech-it
  python -m scripts.sync_pyqs --branch btech-aiml
  python -m scripts.sync_pyqs --branch mbatech
Exit code: 0 = all success, 1 = any failures.
"""
import argparse
import logging
import sys
from typing import Optional
from scripts import pyq_scraper, drive_uploader
from backend.config import GOOGLE_DRIVE_FOLDER_NAME

# Branch keyword sets — each parallel process targets one slot
_BRANCH_SLOTS: dict = {
    "btech-ce":   {"CE", "COMPUTER ENG", "COMPUTER ENGINEERING"},
    "btech-cs":   {"CS", "COMPUTER SCIENCE"},
    "btech-it":   {"INFORMATION TECH", "INFORMATION TECHNOLOGY"},
    "btech-aiml": {"AIML", "AI & ML", "AI AND ML", "ARTIFICIAL INTELLIGENCE"},
    # mbatech → no B TECH override; restrict to MBA TECH program only
    "mbatech":    None,
}

logger = logging.getLogger(__name__)


def main(branch: Optional[str] = None) -> int:
    label = f"[{branch}] " if branch else ""
    logger.info("=== PYQ Sync started %s===", label)

    # Authenticate Drive upfront so the OAuth browser opens before scraping begins
    try:
        service = drive_uploader.authenticate()
        root_id = drive_uploader.get_or_create_folder(
            service, GOOGLE_DRIVE_FOLDER_NAME, parent_id="root"
        )
        logger.info("Drive ready. Root folder: %s", GOOGLE_DRIVE_FOLDER_NAME)
    except Exception as e:
        logger.error("Drive authentication failed: %s", e)
        return 1

    # Load registry of already-uploaded files — lets restarts skip them instantly
    uploaded_registry = drive_uploader.load_uploaded_registry()
    logger.info("Resume registry: %d files already uploaded", len(uploaded_registry))

    upload_counts = {"uploaded": 0, "skipped": 0, "failed": 0}

    def on_file_ready(local_path):
        """Called immediately after each file is downloaded (or found already local)."""
        try:
            result = drive_uploader.upload_and_delete(service, local_path, root_id)
        except Exception as exc:
            logger.warning("Upload failed for %s: %s", local_path.name, exc)
            upload_counts["failed"] += 1
            return
        upload_counts[result] += 1
        if result in ("uploaded", "skipped"):
            rel = str(local_path.relative_to(drive_uploader.PYQ_DIR))
            drive_uploader.mark_as_uploaded(rel)
            uploaded_registry.add(rel)

    branch_override = _BRANCH_SLOTS.get(branch) if branch else None
    try:
        scraper_counts = pyq_scraper.run(
            on_downloaded=on_file_ready,
            skip_paths=uploaded_registry,
            branch_override=branch_override,
            only_programs={"MBA TECH"} if branch == "mbatech" else None,
        )
    except RuntimeError as e:
        logger.error("Scraper failed: %s", e)
        scraper_counts = {"downloaded": 0, "skipped": 0, "failed": 1}

    print(
        f"\nScraper:  {scraper_counts['downloaded']} downloaded, "
        f"{scraper_counts['skipped']} skipped, "
        f"{scraper_counts['failed']} failed"
    )
    print(
        f"Uploader: {upload_counts['uploaded']} uploaded, "
        f"{upload_counts['skipped']} skipped, "
        f"{upload_counts['failed']} failed"
    )

    any_failures = scraper_counts["failed"] > 0 or upload_counts["failed"] > 0
    exit_code = 1 if any_failures else 0
    logger.info("=== PYQ Sync %scomplete (exit %d) ===", label, exit_code)
    return exit_code


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Sync PYQs from SVKM portal to Google Drive")
    parser.add_argument(
        "--branch",
        choices=list(_BRANCH_SLOTS.keys()),
        default=None,
        help="Restrict to one branch slot for parallel execution (omit to sync all)",
    )
    args = parser.parse_args()
    sys.exit(main(branch=args.branch))
