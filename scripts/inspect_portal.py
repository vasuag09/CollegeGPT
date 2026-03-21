"""
One-off portal inspection script — NOT for production.
Run once to discover CSS selectors. Remove after Task 3.
Usage: python scripts/inspect_portal.py
"""
from playwright.sync_api import sync_playwright
from backend.config import SVKM_PORTAL_URL, SVKM_USERNAME, SVKM_PASSWORD


def inspect():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(SVKM_PORTAL_URL)

        # NOTE: these selectors are best-guess for inspection only.
        # Replace them with correct selectors found via DevTools if these fail.
        username_field = page.query_selector("input[name='username']") or page.query_selector("input[type='text']")
        password_field = page.query_selector("input[name='password']") or page.query_selector("input[type='password']")
        if username_field:
            username_field.fill(SVKM_USERNAME)
        if password_field:
            password_field.fill(SVKM_PASSWORD)
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)

        print("URL after login:", page.url)
        print("Title:", page.title())
        print("\nManually navigate to Library → Question Papers.")
        print("When the list is visible, press Enter to dump the DOM.")
        input()

        html = page.inner_html("body")
        print("=== BODY HTML (first 5000 chars) ===")
        print(html[:5000])

        print("\n=== ALL LINKS ===")
        links = page.eval_on_selector_all(
            "a", "els => els.map(e => ({text: e.innerText.trim(), href: e.href}))"
        )
        for link in links[:40]:
            print(link)

        input("\nPress Enter to close.")
        browser.close()


if __name__ == "__main__":
    inspect()
