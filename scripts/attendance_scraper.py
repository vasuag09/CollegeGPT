"""
NM-GPT – SAP NetWeaver Attendance Scraper

Logs into the SAP NetWeaver portal with student-provided credentials,
navigates to the attendance page, and returns subject-wise attendance.

SECURITY: Credentials are NEVER logged or stored. They are used only for
the duration of this function call and discarded immediately after.

Usage (from orchestrator):
    from scripts.attendance_scraper import fetch_attendance
    subjects = fetch_attendance("sapid", "password")
    # [{"subject": "DBMS", "percentage": 78.5}, ...]

Raises RuntimeError on login failure. Do NOT retry automatically —
SAP portals lock accounts after repeated failed logins.
"""

import logging
import re

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from backend.config import SAP_PORTAL_URL

logger = logging.getLogger(__name__)


def fetch_attendance(sap_id: str, sap_password: str) -> list[dict]:
    """
    Log into SAP NetWeaver and scrape subject-wise attendance.

    Returns:
        list of {"subject": str, "percentage": float}

    Raises:
        RuntimeError: on login failure or missing portal URL.
                      Do NOT retry — account lockout risk.
    """
    if not SAP_PORTAL_URL:
        raise RuntimeError(
            "SAP_PORTAL_URL is not configured. "
            "Add SAP_PORTAL_URL to your .env file and restart the server."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            _login(page, sap_id, sap_password)
            subjects = _scrape_attendance(page)
            logger.info("Attendance scraped: %d subjects for %s***", len(subjects), sap_id[:4])
            return subjects
        finally:
            browser.close()


def _login(page, sap_id: str, sap_password: str) -> None:
    """
    Log into the SAP NetWeaver portal.

    Raises RuntimeError on failure — do NOT retry to avoid account lockout.
    Credentials are never passed to the logger.
    """
    logger.info("Navigating to SAP portal...")
    page.goto(SAP_PORTAL_URL, wait_until="domcontentloaded", timeout=20_000)

    # Wait for login form
    try:
        page.wait_for_selector("input[type='text'], input[name*='user'], input[id*='user']", timeout=10_000)
    except PlaywrightTimeout:
        raise RuntimeError(
            "SAP login page did not load. "
            "Check SAP_PORTAL_URL in your .env file."
        )

    # Fill SAP ID
    username_field = (
        page.query_selector("input[name='sap-user']")
        or page.query_selector("input[name='j_username']")
        or page.query_selector("input[id='USERNAME_FIELD-inner']")
        or page.query_selector("input[type='text']")
    )
    # Fill password
    password_field = (
        page.query_selector("input[name='sap-password']")
        or page.query_selector("input[name='j_password']")
        or page.query_selector("input[id='PASSWORD_FIELD-inner']")
        or page.query_selector("input[type='password']")
    )

    if not username_field or not password_field:
        raise RuntimeError(
            "SAP login form fields not found. "
            "Run scripts/inspect_attendance_portal.py to discover the correct selectors."
        )

    username_field.fill(sap_id)
    password_field.fill(sap_password)
    page.keyboard.press("Enter")

    # Wait for redirect away from login page
    try:
        page.wait_for_url(
            lambda url: "login" not in url.lower() and SAP_PORTAL_URL not in url,
            timeout=20_000,
        )
    except PlaywrightTimeout:
        raise RuntimeError(
            "SAP login failed — portal did not redirect after login. "
            "Check your SAP credentials. Do NOT retry automatically to avoid account lockout."
        )

    logger.info("SAP login successful for %s***", sap_id[:4])


def _scrape_attendance(page) -> list[dict]:
    """
    Navigate to the attendance page and extract subject-wise percentages.

    Returns list of {"subject": str, "percentage": float}.
    If the attendance page cannot be found, raises RuntimeError.
    """
    # Navigate to attendance — try common SAP NetWeaver student attendance paths
    attendance_url_candidates = [
        f"{SAP_PORTAL_URL.rstrip('/')}/attendance",
        f"{SAP_PORTAL_URL.rstrip('/')}/student/attendance",
    ]

    # First try clicking an "Attendance" link/menu item on the current page
    attendance_link = (
        page.query_selector("a:has-text('Attendance')")
        or page.query_selector("a:has-text('attendance')")
        or page.query_selector("[title*='Attendance']")
    )

    if attendance_link:
        attendance_link.click()
        page.wait_for_load_state("domcontentloaded", timeout=15_000)
    else:
        # Try navigating directly
        navigated = False
        for url in attendance_url_candidates:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=10_000)
                navigated = True
                break
            except Exception:
                continue
        if not navigated:
            raise RuntimeError(
                "Could not navigate to the attendance page. "
                "Run scripts/inspect_attendance_portal.py to map the correct URL and selectors."
            )

    # Wait for table to load
    try:
        page.wait_for_selector("table, .attendance, [class*='attendance']", timeout=10_000)
    except PlaywrightTimeout:
        raise RuntimeError(
            "Attendance table did not load. "
            "The portal structure may differ from expected — "
            "run scripts/inspect_attendance_portal.py to inspect it."
        )

    return _extract_table(page)


def _extract_table(page) -> list[dict]:
    """
    Extract subject name and attendance percentage from the attendance table.

    Tries common table structures used by SAP NetWeaver student portals.
    Returns list of {"subject": str, "percentage": float}.
    """
    rows = page.query_selector_all("table tr")
    subjects = []

    for row in rows:
        cells = row.query_selector_all("td")
        if len(cells) < 2:
            continue

        cell_texts = [c.inner_text().strip() for c in cells]

        # Look for a cell that contains a percentage value
        pct_value = None
        subject_name = None
        for i, text in enumerate(cell_texts):
            # Match "78.5" or "78.5%" or "78 %" patterns
            match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%?$", text)
            if match:
                val = float(match.group(1))
                if 0 <= val <= 100:
                    pct_value = val
                    # Subject name is typically the first or second cell
                    subject_name = cell_texts[0] if i > 0 else (cell_texts[1] if len(cell_texts) > 1 else None)
                    break

        if subject_name and pct_value is not None:
            # Skip header rows that got through
            if subject_name.lower() in {"subject", "course", "name", "sl.no", "sr.no", "#"}:
                continue
            subjects.append({"subject": subject_name, "percentage": pct_value})

    if not subjects:
        # Fallback: try extracting from any element with percentage-like text
        logger.warning("Standard table extraction found 0 rows — check portal structure")

    return subjects
