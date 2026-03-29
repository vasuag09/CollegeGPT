"""
One-off Playwright script to inspect the SAP NetWeaver attendance portal.
Run this interactively to discover the correct CSS selectors and URL structure,
then update scripts/attendance_scraper.py with the real selectors.

Usage:
    python -m scripts.inspect_attendance_portal

Requires: SAP_PORTAL_URL in .env, and valid SAP credentials via stdin.

Output files (written to data/portal_inspection/):
  login_page.html         — raw HTML of the login page (before login)
  post_login_page.html    — raw HTML after successful login
  attendance_page.html    — raw HTML of the attendance page (if found)
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright
from backend.config import SAP_PORTAL_URL

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "portal_inspection"


def _dump_html(page, filename: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / filename
    path.write_text(page.content(), encoding="utf-8")
    print(f"  [saved] {path}")


def _print_inputs(page) -> None:
    print("\n=== ALL INPUT FIELDS ===")
    for el in page.query_selector_all("input"):
        name = el.get_attribute("name") or ""
        id_ = el.get_attribute("id") or ""
        type_ = el.get_attribute("type") or "text"
        placeholder = el.get_attribute("placeholder") or ""
        print(f"  type={type_!r:12s}  name={name!r:30s}  id={id_!r:30s}  placeholder={placeholder!r}")


def _print_links(page, label: str, limit: int = 40) -> None:
    print(f"\n=== {label} (first {limit}) ===")
    for link in page.query_selector_all("a")[:limit]:
        text = link.inner_text().strip()
        href = link.get_attribute("href") or ""
        if text:
            print(f"  {text!r:50s}  href={href!r}")


def _print_attendance_links(page) -> None:
    print("\n=== ATTENDANCE-RELATED LINKS ===")
    found = False
    for link in page.query_selector_all("a"):
        text = link.inner_text().strip().lower()
        if "attend" in text or "present" in text:
            href = link.get_attribute("href") or ""
            print(f"  text={link.inner_text().strip()!r}  href={href!r}")
            found = True
    if not found:
        print("  (none found — check post_login_page.html for the full structure)")


def _print_tables(page) -> None:
    print("\n=== TABLES ON PAGE ===")
    tables = page.query_selector_all("table")
    print(f"  Found {len(tables)} table(s)")
    for i, table in enumerate(tables[:5]):
        rows = table.query_selector_all("tr")
        print(f"\n  Table {i + 1} ({len(rows)} rows):")
        for row in rows[:5]:
            cells = [c.inner_text().strip() for c in row.query_selector_all("td, th")]
            if cells:
                print(f"    {cells}")


def main():
    if not SAP_PORTAL_URL:
        print("ERROR: SAP_PORTAL_URL is not set in .env")
        sys.exit(1)

    print(f"Portal URL: {SAP_PORTAL_URL}")
    sap_id = input("SAP ID: ").strip()
    sap_password = getpass.getpass("SAP Password: ")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # visible for manual inspection
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.new_page(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # ── Step 1: Login page ───────────────────────────────────
        print(f"\nNavigating to: {SAP_PORTAL_URL}")
        # Use "load" (not "domcontentloaded") so onload fires and Captcha() runs
        page.goto(SAP_PORTAL_URL, wait_until="load", timeout=30_000)
        print(f"Login page URL: {page.url}")
        _dump_html(page, "login_page.html")
        _print_inputs(page)

        # ── Step 2: Fill and submit login ────────────────────────
        page.fill("#logonuidfield", sap_id)
        page.fill("#logonpassfield", sap_password)

        # Poll for captcha code — Captcha() runs onload, wait up to 3s
        try:
            page.wait_for_function(
                "() => typeof window.code === 'string' && window.code.length > 0",
                timeout=3000,
            )
            captcha_code = page.evaluate("() => window.code")
            print(f"\nCAPTCHA resolved from JS: {captcha_code!r}")
        except Exception:
            captcha_code = None
            print("\nWARNING: window.code not set — CAPTCHA may need manual entry")

        if captcha_code:
            page.fill("#txtInput", captcha_code)
        else:
            captcha_code = input("Enter the CAPTCHA shown in the browser: ").strip()
            page.fill("#txtInput", captcha_code)

        print("Clicking Log On...")
        page.click("#Button1")
        # Wait for page to settle after login
        try:
            page.wait_for_load_state("networkidle", timeout=20_000)
        except Exception:
            page.wait_for_timeout(3000)
        print(f"Post-login URL: {page.url}")
        _dump_html(page, "post_login_page.html")

        # ── Step 3: Inspect post-login page ──────────────────────
        _print_links(page, "POST-LOGIN NAVIGATION LINKS")
        _print_attendance_links(page)
        _print_tables(page)

        # ── Step 4: Try to navigate to attendance ────────────────
        attendance_link = (
            page.query_selector("a:has-text('Attendance Display')")
            or page.query_selector("a:has-text('Attendance')")
            or page.query_selector("[title*='Attendance']")
        )

        if not attendance_link:
            print("\nNo attendance link found on post-login page.")
            print("Check post_login_page.html for the correct navigation structure.")
            input("\nBrowser open for manual inspection. Press Enter to close...")
            browser.close()
            return

        # ── Step 5: Navigate to attendance iView ─────────────────
        print(f"\nFound attendance link — clicking...")
        attendance_link.click()
        print("Waiting 10s for SAP iView to load...")
        page.wait_for_timeout(10_000)
        _dump_html(page, "attendance_page.html")
        print(f"\nAttendance page URL: {page.url}")

        # Find the attendance WebDynpro frame
        attendance_frame = None
        for frame in page.frames:
            if "ZSVKM_STUDENT_ATTENDANCE2" in frame.url:
                attendance_frame = frame
                print(f"\nAttendance frame: {frame.url[:100]}")
                break

        if not attendance_frame:
            print("\nAttendance frame NOT found. Available frames:")
            for i, f in enumerate(page.frames):
                print(f"  [{i}] {f.url!r}")
            input("\nBrowser open. Press Enter to close...")
            browser.close()
            return

        # ── Step 6: Dump initial frame HTML ──────────────────────
        try:
            frame_html = attendance_frame.content()
            (OUT_DIR / "frame_initial.html").write_text(frame_html, encoding="utf-8")
            print(f"  [saved] frame_initial.html ({len(frame_html)} chars)")
        except Exception as e:
            print(f"  Could not save initial frame: {e}")

        # ── Step 7: Fill the form ─────────────────────────────────
        print("\n=== FILLING ATTENDANCE FORM ===")

        # Wait for WD2B (Academic Year ComboBox)
        try:
            attendance_frame.wait_for_selector("#WD2B", timeout=15_000)
            print("  WD2B found — form is ready")
        except Exception:
            print("  WD2B not found within 15s — form may not have rendered")

        def _wd_click(eid):
            attendance_frame.evaluate(f"""
                (function() {{
                    var el = document.getElementById('{eid}');
                    if (!el) {{ console.log('MISSING: {eid}'); return; }}
                    ['mousedown','mouseup','click'].forEach(function(t) {{
                        el.dispatchEvent(new MouseEvent(t, {{bubbles:true, cancelable:true, view:window}}));
                    }});
                }})();
            """)
            print(f"  _wd_click({eid!r})")

        # ── Snapshot semester labels before year click ───────────────
        def _read_sem_opts_frame():
            items = attendance_frame.evaluate("""
                () => {
                    let items = Array.from(document.querySelectorAll('#WD35 .lsListbox__value'));
                    if (items.length > 0) return items.map(el => ({ id: el.id, label: el.innerText.trim() }));
                    items = Array.from(document.querySelectorAll('.lsListbox__value'))
                                 .filter(el => /semester/i.test(el.innerText));
                    return items.map(el => ({ id: el.id, label: el.innerText.trim() }));
                }
            """)
            return items

        prev_labels = frozenset(s["label"] for s in _read_sem_opts_frame())

        # Academic Year
        _wd_click("WD2B")
        page.wait_for_timeout(800)

        year_opts = attendance_frame.evaluate("""
            () => Array.from(document.querySelectorAll('#WD2C .lsListbox__value'))
                       .map(el => ({id: el.id, text: el.innerText.trim(), key: el.getAttribute('data-itemkey')}))
        """)
        print(f"  Year options: {year_opts}")

        if year_opts:
            _wd_click(year_opts[-1]['id'])
        page.wait_for_timeout(500)

        # Wait for semester listbox to change
        for _ in range(40):
            current = frozenset(s["label"] for s in _read_sem_opts_frame())
            if current and current != prev_labels:
                break
            page.wait_for_timeout(500)

        sem_opts = _read_sem_opts_frame()
        print(f"  Semester options: {sem_opts}")

        # Click last semester item directly (no dropdown trigger click)
        if sem_opts:
            _wd_click(sem_opts[-1]['id'])
        page.wait_for_timeout(2000)

        # ── Report type: find trigger dynamically (last ct=CB input) ──
        report_trigger_id = attendance_frame.evaluate("""
            () => {
                const boxes = Array.from(document.querySelectorAll("input[ct='CB']"))
                                   .filter(el => el.id && el.id.startsWith('WD'));
                return boxes.length > 0 ? boxes[boxes.length - 1].id : null;
            }
        """)
        print(f"  Report-type trigger id: {report_trigger_id}")
        if report_trigger_id:
            _wd_click(report_trigger_id)
        page.wait_for_timeout(800)

        # All listbox items visible now
        all_listbox = attendance_frame.evaluate("""
            () => Array.from(document.querySelectorAll('.lsListbox__value'))
                       .map(el => ({id: el.id, text: el.innerText.trim()}))
        """)
        print(f"  All listbox items after opening report-type dropdown: {all_listbox}")

        # Click Detail Report by text
        detail_info = attendance_frame.evaluate("""
            () => {
                for (const el of document.querySelectorAll('.lsListbox__value')) {
                    if (/detail/i.test(el.innerText)) return { id: el.id, text: el.innerText.trim() };
                }
                return null;
            }
        """)
        print(f"  Detail Report item: {detail_info}")
        if detail_info:
            _wd_click(detail_info['id'])
        page.wait_for_timeout(2000)

        # All inputs after Detail selection
        all_inputs_after = attendance_frame.evaluate("""
            () => Array.from(document.querySelectorAll('input'))
                       .filter(el => el.id && el.id.startsWith('WD') && el.type !== 'hidden')
                       .map(el => ({id: el.id, ct: el.getAttribute('ct'), type: el.type, value: el.value, visible: el.offsetParent !== null}))
        """)
        print(f"\n  All inputs after Detail selection:")
        for inp in all_inputs_after:
            print(f"    {inp}")

        date_inputs = [i for i in all_inputs_after if i.get('ct') == 'I']
        if not date_inputs:
            # fallback: any visible text input
            date_inputs = [i for i in all_inputs_after if i.get('type') == 'text' and i.get('visible')]
        print(f"\n  Date inputs: {date_inputs}")

        from datetime import datetime, timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        end_date_str = datetime.now(IST).strftime("%d.%m.%Y")
        if len(date_inputs) >= 2:
            attendance_frame.fill(f"#{date_inputs[0]['id']}", "01.06.2025")
            attendance_frame.fill(f"#{date_inputs[1]['id']}", end_date_str)
            for di in date_inputs[:2]:
                fid = di['id']
                attendance_frame.evaluate(f"""
                    (function() {{
                        var el = document.getElementById('{fid}');
                        if (!el) return;
                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                        el.dispatchEvent(new Event('blur',   {{bubbles: true}}));
                    }})();
                """)
            print(f"  Filled dates: 01.06.2025 → {end_date_str}")
            page.wait_for_timeout(800)
        else:
            print("  WARNING: No date inputs found — submitting without dates")

        # ── Find submit button dynamically (last ct=B input) ─────────
        submit_id = attendance_frame.evaluate("""
            () => {
                if (document.getElementById('WD52')) return 'WD52';
                const btns = Array.from(document.querySelectorAll("input[ct='B']"))
                                  .filter(el => el.id && el.id.startsWith('WD'));
                if (btns.length > 0) return btns[btns.length - 1].id;
                return null;
            }
        """)
        print(f"\n  Submit button id: {submit_id}")

        # ── Step 8: Track ALL responses while submitting ──────────
        print("\n=== SUBMITTING FORM (monitoring all responses) ===")
        response_log = []

        def _log_response(resp):
            ct = resp.headers.get("content-type", "?")
            response_log.append(f"  {resp.status} {ct[:60]:60s} {resp.url[:100]}")

        page.on("response", _log_response)

        if submit_id:
            _wd_click(submit_id)
        else:
            print("  WARNING: Submit button not found!")
        print("  Submit clicked — waiting 30s for response...")
        page.wait_for_timeout(30_000)

        print(f"\n  Responses received ({len(response_log)}):")
        for r in response_log[-30:]:  # last 30
            print(r)

        # ── Step 9: Check frame DOM after submit ──────────────────
        print("\n=== FRAME DOM AFTER SUBMIT ===")
        try:
            post_html = attendance_frame.content()
            (OUT_DIR / "frame_post_submit.html").write_text(post_html, encoding="utf-8")
            print(f"  [saved] frame_post_submit.html ({len(post_html)} chars)")
        except Exception as e:
            print(f"  Could not save post-submit frame: {e}")

        # Check for embed/object/iframe elements
        embeds = attendance_frame.evaluate("""
            () => {
                const results = [];
                for (const sel of ['embed', 'object', 'iframe', 'object[type]', 'embed[type]']) {
                    for (const el of document.querySelectorAll(sel)) {
                        results.push({
                            tag: el.tagName,
                            id: el.id,
                            src: el.src || '',
                            data: el.getAttribute('data') || '',
                            type: el.getAttribute('type') || '',
                            ct: el.getAttribute('ct') || ''
                        });
                    }
                }
                return results;
            }
        """)
        print(f"\n  Embed/object/iframe elements: {embeds}")

        # Check all frames after submit
        print(f"\n  Frames after submit ({len(page.frames)}):")
        for i, frame in enumerate(page.frames):
            print(f"    [{i}] {frame.url[:120]!r}")

        # Print first 3000 chars of post-submit frame text
        try:
            post_text = attendance_frame.evaluate("() => document.body.innerText")
            print(f"\n  Frame body text (first 1000 chars):\n{post_text[:1000]}")
        except Exception as e:
            print(f"  Could not get frame text: {e}")

        print(f"\n{'=' * 60}")
        print(f"HTML files saved to: {OUT_DIR}")
        print(f"{'=' * 60}")

        input("\nBrowser stays open for manual inspection. Press Enter to close...")
        browser.close()


if __name__ == "__main__":
    main()
