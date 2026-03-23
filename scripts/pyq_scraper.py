"""
SVKM Portal → local PYQ downloader.
Playwright sync API. Run via sync_pyqs.py or standalone.

Portal structure (recursive folder tree):
  QUESTIONS PAPERS / <Program> / <Year> / <Semester> / <Subject> / *.pdf

Folder links use:   a[href*='viewLibrary?folderPath=']
File links use:     a[href*='downloadFile']
Download URL:       https://portal.svkm.ac.in/MPSTME-NM-M/downloadFile?libraryId=<N>
"""
import logging
import re
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

from backend.config import (
    SVKM_PORTAL_URL,
    SVKM_USERNAME,
    SVKM_PASSWORD,
    PYQ_DIR,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://portal.svkm.ac.in/MPSTME-NM-M"

# Root URL for the Question Papers library folder.
# parentId=1 is the QUESTIONS PAPERS root (B TECH uses parentId=2 as its own ID).
QP_ROOT_URL = (
    f"{BASE_URL}/viewLibrary"
    "?folderPath=%2fdata%2fMPSTME-NM-M%2flibrary%2fQUESTIONS+PAPERS+&parentId=1"
)

_MAX_RETRIES = 3
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# ── Filters ────────────────────────────────────────────────────────────────────
# depth 0 = program folders (B TECH, MBA TECH, MCA, …)
# depth 1 = branch or year folders within a program
#
# Only these programs are scraped.
ALLOWED_PROGRAMS = {"B TECH", "MBA TECH"}

# Per-program branch keywords (case-insensitive substring match).
# "IT" is handled separately via exact word match (too short for substring).
# Year folders ("1ST YEAR", "2ND YEAR") are always allowed at depth 1.
_BRANCH_KEYWORDS_BY_PROGRAM: dict[str, set] = {
    "B TECH": {
        # Computer Engineering
        "CE", "COMPUTER ENG", "COMPUTER ENGINEERING",
        # Computer Science
        "CS", "COMPUTER SCIENCE",
        # Information Technology
        "INFORMATION TECH", "INFORMATION TECHNOLOGY",
        # AI & ML
        "AIML", "AI & ML", "AI AND ML", "ARTIFICIAL INTELLIGENCE",
    },
    "MBA TECH": {
        # Civil Engineering
        "CE", "CIVIL",
    },
}

# Fallback for any program not listed above (allow all branches)
_DEFAULT_BRANCH_KEYWORDS = None  # type: Optional[set]

# "IT" exact word match — only applies to B TECH
_IT_EXACT = {"IT"}


def _is_allowed(name: str, depth: int, program: str = "", branch_override: Optional[set] = None, allowed_programs: Optional[set] = None) -> bool:
    """Return True if this folder should be recursed into.

    branch_override: if provided, replaces _BRANCH_KEYWORDS_BY_PROGRAM at depth 1
    for B TECH (lets each parallel process target one branch).
    allowed_programs: overrides the global ALLOWED_PROGRAMS set.
    """
    upper = name.upper()
    if depth == 0:
        programs = allowed_programs if allowed_programs is not None else ALLOWED_PROGRAMS
        return upper in {p.upper() for p in programs}
    if depth == 1:
        # Always allow year folders (e.g. "1ST YEAR", "2ND YEAR")
        if "YEAR" in upper:
            return True
        prog_key = program.upper()
        if branch_override is not None and prog_key == "B TECH":
            keywords = branch_override
        else:
            keywords = next(
                (v for k, v in _BRANCH_KEYWORDS_BY_PROGRAM.items() if k.upper() == prog_key),
                _DEFAULT_BRANCH_KEYWORDS,
            )
        if keywords is None:
            return True  # unknown program → allow all branches
        if any(kw in upper for kw in keywords):
            return True
        # Exact word match for "IT" (B TECH only)
        if prog_key == "B TECH" and set(upper.split()) & _IT_EXACT:
            return True
        return False
    return True  # depth ≥ 2: no filtering


def _sanitize(name: str) -> str:
    """Strip characters that are invalid in file/directory names."""
    return _INVALID_CHARS.sub("_", name.strip()).strip()


def _login(page: Page) -> None:
    """Log in to the SVKM portal. Raises RuntimeError on failure — do NOT retry."""
    if not SVKM_USERNAME or not SVKM_PASSWORD:
        raise RuntimeError("SVKM_USERNAME and SVKM_PASSWORD must be set in .env")

    page.goto(SVKM_PORTAL_URL, wait_until="domcontentloaded")
    page.wait_for_selector("input[name='username'], input[type='text']", timeout=10_000)

    username_field = (
        page.query_selector("input[name='username']")
        or page.query_selector("input[type='text']")
    )
    password_field = (
        page.query_selector("input[name='password']")
        or page.query_selector("input[type='password']")
    )
    if not username_field or not password_field:
        raise RuntimeError("Login form not found — portal structure may have changed.")

    username_field.fill(SVKM_USERNAME)
    password_field.fill(SVKM_PASSWORD)
    page.keyboard.press("Enter")
    try:
        page.wait_for_url("**/homepage**", timeout=20_000)
    except PlaywrightTimeout:
        raise RuntimeError(
            "Login failed — portal did not redirect to homepage. "
            "Check SVKM_USERNAME and SVKM_PASSWORD in .env. "
            "Do NOT retry automatically to avoid account lockout."
        )
    logger.info("Login successful. URL: %s", page.url)


def _download_file(page: Page, url: str, dest: Path, counts: dict, on_downloaded=None, skip_paths: set = None) -> None:
    """Download a single file using the authenticated session (page.request carries cookies)."""
    rel = str(dest.relative_to(PYQ_DIR))
    if skip_paths and rel in skip_paths:
        logger.info("Skipped (already uploaded): %s", rel)
        counts["skipped"] += 1
        return
    if dest.exists():
        logger.info("Skipped (exists locally): %s", rel)
        counts["skipped"] += 1
        if on_downloaded:
            on_downloaded(dest)
        return

    dest.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = page.request.get(url, timeout=60_000)
            if response.status != 200:
                logger.warning("HTTP %d for %s (attempt %d)", response.status, url, attempt)
            else:
                dest.write_bytes(response.body())
                logger.info("Downloaded: %s", dest.relative_to(PYQ_DIR))
                counts["downloaded"] += 1
                if on_downloaded:
                    on_downloaded(dest)
                return
        except Exception as exc:
            logger.warning("Download error (attempt %d/%d): %s", attempt, _MAX_RETRIES, exc)
        if attempt < _MAX_RETRIES:
            time.sleep(2 ** attempt)

    logger.warning("Failed after %d attempts: %s", _MAX_RETRIES, url)
    counts["failed"] += 1


def _scrape_folder(page: Page, folder_url: str, local_dir: Path, counts: dict, depth: int = 0, on_downloaded=None, skip_paths: set = None, program: str = "", branch_override: Optional[set] = None, allowed_programs: Optional[set] = None) -> None:
    """
    Recursively scrape a folder page.
    - Rows with viewLibrary links → sub-folders (recurse)
    - Rows with downloadFile links → files (download)
    """
    logger.info("Visiting folder: %s", folder_url)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            page.goto(folder_url, timeout=30_000, wait_until="domcontentloaded")
            # Wait for the table to appear — much faster than networkidle
            page.wait_for_selector("table", timeout=10_000)
            break
        except Exception as exc:
            if attempt == _MAX_RETRIES:
                logger.warning("Could not load folder after %d attempts: %s — skipping", _MAX_RETRIES, exc)
                counts["failed"] += 1
                return
            time.sleep(2 ** attempt)

    # Sub-folders: table cells containing viewLibrary links
    folder_links = page.eval_on_selector_all(
        "table tr td a[href*='viewLibrary?folderPath=']",
        "els => els.map(e => ({text: e.innerText.trim(), href: e.href}))",
    )

    # Files: table cells containing downloadFile links
    file_links = page.eval_on_selector_all(
        "table tr td a[href*='downloadFile']",
        "els => els.map(e => ({text: e.innerText.trim(), href: e.href}))",
    )

    for folder in folder_links:
        name = _sanitize(folder["text"])
        if not name:
            continue
        # At depth 0 the folder name is the program; pass it down for branch filtering
        current_program = name if depth == 0 else program
        if not _is_allowed(name, depth, program, branch_override, allowed_programs):
            logger.info("Skipping (filtered): %s", name)
            continue
        _scrape_folder(page, folder["href"], local_dir / name, counts, depth + 1, on_downloaded, skip_paths, current_program, branch_override, allowed_programs)

    for file_info in file_links:
        filename = _sanitize(file_info["text"])
        if not filename:
            continue
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        _download_file(page, file_info["href"], local_dir / filename, counts, on_downloaded, skip_paths)


def run(on_downloaded=None, skip_paths: set = None, branch_override: Optional[set] = None, only_programs: Optional[set] = None) -> dict:
    """
    Main entry point.
    Returns {"downloaded": int, "skipped": int, "failed": int}.
    Raises RuntimeError on login failure (caller must not retry).
    branch_override: if provided, restricts B TECH scraping to folders matching
    these keywords at depth 1 (used to parallelise across branches).
    only_programs: if provided, overrides ALLOWED_PROGRAMS for this run.
    """
    counts = {"downloaded": 0, "skipped": 0, "failed": 0}
    effective_programs = only_programs if only_programs is not None else ALLOWED_PROGRAMS

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # portal detects headless; run headed
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        try:
            _login(page)
            _scrape_folder(page, QP_ROOT_URL, PYQ_DIR, counts, on_downloaded=on_downloaded, skip_paths=skip_paths, branch_override=branch_override, allowed_programs=effective_programs)
        finally:
            context.close()
            browser.close()

    logger.info(
        "Scraper done — downloaded: %d, skipped: %d, failed: %d",
        counts["downloaded"], counts["skipped"], counts["failed"],
    )
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print(run())
