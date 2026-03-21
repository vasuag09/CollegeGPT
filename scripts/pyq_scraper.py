"""
SVKM Portal → local PYQ downloader.
Playwright sync API. Run via sync_pyqs.py or standalone.
"""
import logging
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from backend.config import (
    SVKM_PORTAL_URL,
    SVKM_USERNAME,
    SVKM_PASSWORD,
    PYQ_DIR,
)

logger = logging.getLogger(__name__)

# ── Selectors — fill in from Task 2 inspection ────────────────
# Set SELECTOR_NEXT_PAGE = None if there is no pagination (not the placeholder string).
SELECTOR_POST_LOGIN   = "<SELECTOR_POST_LOGIN>"
SELECTOR_LIBRARY_LINK = "<SELECTOR_LIBRARY_LINK>"
SELECTOR_QP_LINK      = "<SELECTOR_QP_LINK>"
SELECTOR_QP_ROW       = "<SELECTOR_QP_ROW>"
SELECTOR_SUBJECT      = "<SELECTOR_SUBJECT>"
SELECTOR_YEAR         = "<SELECTOR_YEAR>"
SELECTOR_SEMESTER     = "<SELECTOR_SEMESTER>"
SELECTOR_DOWNLOAD     = "<SELECTOR_DOWNLOAD>"
SELECTOR_NEXT_PAGE    = None   # set to selector string if paginated, else None

_MAX_RETRIES = 3


def _sanitize(name: str) -> str:
    """Make a string safe for use as a directory name."""
    return "".join(c if c.isalnum() or c in " -_()" else "_" for c in name).strip()


def _filename_from_url(url: str) -> str:
    """
    Extract a usable filename from a URL.
    Handles both clean paths (/files/exam.pdf) and query-string URLs (?file=exam.pdf).
    URL-decodes the result to handle encoded characters.
    """
    parsed = urlparse(url)
    # Try query parameter named 'file' or 'filename' first
    for key in ("file", "filename", "name"):
        val = parse_qs(parsed.query).get(key, [None])[0]
        if val:
            return unquote(val.split("/")[-1])
    # Fall back to last path segment
    segment = parsed.path.split("/")[-1]
    if segment and "." in segment:
        return unquote(segment)
    return ""


def _download_with_retry(page, url: str, dest: Path) -> bool:
    """
    Download a file using page.request (carries auth cookies).
    Retries up to _MAX_RETRIES times with exponential backoff.
    Returns True on success, False on failure.
    """
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = page.request.get(url, timeout=60_000)
            if response.status != 200:
                logger.warning("HTTP %d for %s (attempt %d)", response.status, url, attempt)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(response.body())
                return True
        except Exception as e:
            logger.warning("Download error (attempt %d/%d): %s", attempt, _MAX_RETRIES, e)
        if attempt < _MAX_RETRIES:
            time.sleep(2 ** attempt)
    return False


def _login(page) -> None:
    """Log in to the SVKM portal. Raises RuntimeError on failure — do NOT retry."""
    if not SVKM_USERNAME or not SVKM_PASSWORD:
        raise RuntimeError("SVKM_USERNAME and SVKM_PASSWORD must be set in .env")
    page.goto(SVKM_PORTAL_URL)
    page.fill("input[name='username']", SVKM_USERNAME)
    page.fill("input[name='password']", SVKM_PASSWORD)
    page.keyboard.press("Enter")
    try:
        page.wait_for_selector(SELECTOR_POST_LOGIN, timeout=10_000)
    except PlaywrightTimeout:
        raise RuntimeError(
            "Login failed — post-login element not found. "
            "Check SVKM_USERNAME/SVKM_PASSWORD in .env. "
            "Do NOT retry — repeated failures may lock the account."
        )
    logger.info("Login successful")


def _navigate_to_question_papers(page) -> None:
    """Navigate to Library → Question Papers and wait for the list to load."""
    page.click(SELECTOR_LIBRARY_LINK)
    page.click(SELECTOR_QP_LINK)
    page.wait_for_selector(SELECTOR_QP_ROW, timeout=15_000)
    logger.info("Question Papers page loaded")


def _scrape_page(page, counts: dict) -> None:
    """Scrape all rows on the current question papers page."""
    rows = page.query_selector_all(SELECTOR_QP_ROW)
    for row in rows:
        try:
            subject_el = row.query_selector(SELECTOR_SUBJECT)
            if subject_el is None:
                logger.warning("Subject element not found in row — skipping")
                counts["failed"] += 1
                continue
            subject = _sanitize(subject_el.inner_text())

            year_el = row.query_selector(SELECTOR_YEAR)
            if year_el is None:
                logger.warning("Year element not found in row — skipping")
                counts["failed"] += 1
                continue
            year = _sanitize(year_el.inner_text())

            semester_el = row.query_selector(SELECTOR_SEMESTER)
            if semester_el is None:
                logger.warning("Semester element not found in row — skipping")
                counts["failed"] += 1
                continue
            semester = _sanitize(semester_el.inner_text())

            dl_el = row.query_selector(SELECTOR_DOWNLOAD)
            if dl_el is None:
                logger.warning("Download element not found in row — skipping")
                counts["failed"] += 1
                continue
            url = dl_el.get_attribute("href")

            if not url:
                logger.warning("No href found on download element — may be JS-triggered (row skipped)")
                counts["failed"] += 1
                continue

            filename = _filename_from_url(url) or f"{subject}_{year}_{semester}.pdf"
            if not filename.endswith(".pdf"):
                filename += ".pdf"
            dest = PYQ_DIR / subject / year / semester / filename

            if dest.exists():
                logger.info("Skipping (exists): %s", dest.relative_to(PYQ_DIR))
                counts["skipped"] += 1
                continue

            logger.info("Downloading: %s", dest.relative_to(PYQ_DIR))
            ok = _download_with_retry(page, url, dest)
            counts["downloaded" if ok else "failed"] += 1

        except Exception as e:
            logger.warning("Failed to process row: %s", e)
            counts["failed"] += 1


def _relogin_and_navigate(page) -> None:
    """Re-login after session expiry. Raises RuntimeError if re-login fails."""
    logger.warning("Session may have expired — attempting re-login")
    _login(page)   # raises RuntimeError on auth failure — do not catch
    _navigate_to_question_papers(page)


def run() -> dict:
    """
    Main entry point.
    Returns {"downloaded": int, "skipped": int, "failed": int}.
    Raises RuntimeError on login failure (caller must not retry).
    """
    counts = {"downloaded": 0, "skipped": 0, "failed": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        _login(page)
        _navigate_to_question_papers(page)

        while True:
            try:
                _scrape_page(page, counts)
            except PlaywrightTimeout:
                # Page may have expired — re-login once, then retry this page
                try:
                    _relogin_and_navigate(page)
                    _scrape_page(page, counts)
                except (PlaywrightTimeout, RuntimeError) as e:
                    logger.error("Session recovery failed: %s", e)
                    raise

            if SELECTOR_NEXT_PAGE is None:
                break
            next_btn = page.query_selector(SELECTOR_NEXT_PAGE)
            if not next_btn or not next_btn.is_visible():
                break
            next_btn.click()
            page.wait_for_selector(SELECTOR_QP_ROW, timeout=10_000)

        browser.close()

    logger.info(
        "Scraper done — downloaded: %d, skipped: %d, failed: %d",
        counts["downloaded"], counts["skipped"], counts["failed"],
    )
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print(run())
