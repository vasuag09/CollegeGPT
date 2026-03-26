"""
One-off portal inspection script — NOT for production.
Run once to discover CSS selectors. Remove after selectors are filled in.
Usage: python scripts/inspect_portal.py
"""
from playwright.sync_api import sync_playwright
from backend.config import SVKM_PORTAL_URL, SVKM_USERNAME, SVKM_PASSWORD


def inspect():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(SVKM_PORTAL_URL)

        username_field = page.query_selector("input[name='username']") or page.query_selector("input[type='text']")
        password_field = page.query_selector("input[name='password']") or page.query_selector("input[type='password']")
        if username_field:
            username_field.fill(SVKM_USERNAME)
        if password_field:
            password_field.fill(SVKM_PASSWORD)
        page.keyboard.press("Enter")
        page.wait_for_load_state("networkidle", timeout=15000)

        print("URL after login:", page.url)

        # Verify the QP root URL (parentId=1 assumed)
        QP_ROOT = "https://portal.svkm.ac.in/MPSTME-NM-M/viewLibrary?folderPath=%2fdata%2fMPSTME-NM-M%2flibrary%2fQUESTIONS+PAPERS+&parentId=1"
        print("Navigating to QP root...")
        page.goto(QP_ROOT)
        page.wait_for_load_state("networkidle", timeout=15000)
        print("URL after navigation:", page.url)

        print("\n=== QP ROOT TABLE ROWS ===")
        rows = page.query_selector_all("tr")
        for row in rows:
            text = row.inner_text().strip()
            if text:
                print(text)
                print("---")

        print("\n=== QP ROOT FOLDER LINKS ===")
        folder_links = page.eval_on_selector_all(
            "table tr td a[href*='viewLibrary?folderPath=']",
            "els => els.map(e => ({text: e.innerText.trim(), href: e.href}))"
        )
        for link in folder_links:
            print(link)

        print("\n=== QP ROOT FILE LINKS ===")
        file_links = page.eval_on_selector_all(
            "table tr td a[href*='downloadFile']",
            "els => els.map(e => ({text: e.innerText.trim(), href: e.href}))"
        )
        for link in file_links:
            print(link)

        input("\nPress Enter to close.")
        browser.close()


if __name__ == "__main__":
    inspect()
