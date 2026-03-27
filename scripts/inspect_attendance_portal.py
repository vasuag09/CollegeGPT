"""
One-off Playwright script to inspect the SAP NetWeaver attendance portal.
Run this interactively to discover the correct CSS selectors and URL structure
before the attendance scraper will work.

Usage:
    python -m scripts.inspect_attendance_portal

Requires: SAP_PORTAL_URL in .env, and valid SAP credentials via stdin.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright
from backend.config import SAP_PORTAL_URL


def main():
    if not SAP_PORTAL_URL:
        print("ERROR: SAP_PORTAL_URL is not set in .env")
        sys.exit(1)

    sap_id = input("SAP ID: ").strip()
    sap_password = getpass.getpass("SAP Password: ")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # visible for inspection
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        print(f"\nNavigating to: {SAP_PORTAL_URL}")
        page.goto(SAP_PORTAL_URL, wait_until="domcontentloaded")

        print("\n=== LOGIN FORM FIELDS ===")
        for sel in ["input[type='text']", "input[type='password']", "input[name*='user']", "input[name*='pass']"]:
            els = page.query_selector_all(sel)
            for el in els:
                name = el.get_attribute("name") or ""
                id_ = el.get_attribute("id") or ""
                type_ = el.get_attribute("type") or ""
                print(f"  selector={sel!r}  name={name!r}  id={id_!r}  type={type_!r}")

        # Fill credentials
        username_field = page.query_selector("input[type='text']") or page.query_selector("input[name*='user']")
        password_field = page.query_selector("input[type='password']") or page.query_selector("input[name*='pass']")

        if username_field:
            username_field.fill(sap_id)
        if password_field:
            password_field.fill(sap_password)

        print("\nSubmitting login form (Enter)...")
        page.keyboard.press("Enter")
        page.wait_for_load_state("domcontentloaded", timeout=20_000)
        print(f"Post-login URL: {page.url}")

        print("\n=== NAVIGATION LINKS (first 30) ===")
        links = page.query_selector_all("a")
        for link in links[:30]:
            text = link.inner_text().strip()
            href = link.get_attribute("href") or ""
            if text:
                print(f"  {text!r:40s}  href={href!r}")

        # Try to find attendance link
        print("\n=== ATTENDANCE-RELATED LINKS ===")
        for link in page.query_selector_all("a"):
            text = link.inner_text().strip().lower()
            if "attend" in text:
                href = link.get_attribute("href") or ""
                print(f"  text={link.inner_text().strip()!r}  href={href!r}")

        input("\nBrowser is open — inspect manually. Press Enter to close...")
        browser.close()


if __name__ == "__main__":
    main()
