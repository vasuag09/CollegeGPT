"""
NM-GPT – SAP NetWeaver Attendance Scraper

Logs into the SAP NetWeaver portal with student-provided credentials,
navigates to the attendance page, fills the Detail Report form, intercepts
the generated PDF, and returns subject-wise attendance computed from it.

SECURITY: Credentials are NEVER logged or stored. They are used only for
the duration of this function call and discarded immediately after.

Usage (from orchestrator):
    from scripts.attendance_scraper import fetch_attendance
    subjects = fetch_attendance("sapid", "password")
    # [{"subject": "Machine Learning", "percentage": 86.0}, ...]

Raises RuntimeError on login failure. Do NOT retry automatically —
SAP portals lock accounts after repeated failed logins.
"""

import json
import logging
import math
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import fitz  # PyMuPDF
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from backend.config import COURSE_DURATIONS_PATH, SAP_PORTAL_URL

logger = logging.getLogger(__name__)

# SAP portal access window (IST = UTC+5:30)
_IST = timezone(timedelta(hours=5, minutes=30))
_PORTAL_OPEN_HOUR = 18   # 6:00 PM IST
_PORTAL_CLOSE_HOUR = 7   # 7:00 AM IST

# Academic year start date for the Detail Report (DD.MM.YYYY)
_AY_START_DATE = "01.06.2025"

# Statuses that count as "present"
_PRESENT_STATUSES = {"P", "E", "L"}   # Present, Exemption, Late admission
_VALID_STATUSES = {"P", "A", "E", "L", "NU"}

# Regex to detect a month-name at the start of a PDF date cell
_MONTH_RE = re.compile(
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d"
)


def _check_portal_window() -> None:
    """Raise RuntimeError if outside the SAP portal access window (6 PM – 7 AM IST)."""
    now_ist = datetime.now(_IST)
    hour = now_ist.hour
    # Portal is open from 18:00 to 06:59 IST (spans midnight)
    if _PORTAL_CLOSE_HOUR <= hour < _PORTAL_OPEN_HOUR:
        open_time = now_ist.replace(hour=_PORTAL_OPEN_HOUR, minute=0, second=0, microsecond=0)
        raise RuntimeError(
            f"The SAP portal is only accessible between 6:00 PM and 7:00 AM IST. "
            f"Current IST time: {now_ist.strftime('%I:%M %p')}. "
            f"Please try again after {open_time.strftime('%I:%M %p')} IST."
        )


def fetch_attendance_options(sap_id: str, sap_password: str) -> dict:
    """
    Log into SAP NetWeaver and return the available academic years and semesters
    for the student without fetching attendance data.

    Returns:
        {
          "years": [{"key": "2025", "label": "2025-2026"}, ...],   # oldest→newest
          "semesters": [{"label": "Semester V"}, {"label": "Semester VI"}],
          "default_year": "2025",
          "default_semester": "Semester VI",
        }

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

            try:
                attendance_link = page.wait_for_selector(
                    "a:has-text('Attendance Display for Students')",
                    timeout=30_000,
                )
            except PlaywrightTimeout:
                raise RuntimeError(
                    "Attendance link not found after 30 s. "
                    "The portal navigation may still be loading — please try again."
                )
            attendance_link.click()

            # Wait for the WebDynpro frame
            attendance_frame = None
            for _ in range(60):
                for frame in page.frames:
                    if "ZSVKM_STUDENT_ATTENDANCE2" in frame.url:
                        attendance_frame = frame
                        break
                if attendance_frame:
                    break
                page.wait_for_timeout(500)

            if not attendance_frame:
                raise RuntimeError(
                    "Attendance form did not load within 30 seconds."
                )

            try:
                attendance_frame.wait_for_selector("#WD2B", timeout=30_000)
            except PlaywrightTimeout:
                raise RuntimeError(
                    "Attendance form did not render within 30 seconds."
                )
            attendance_frame.wait_for_timeout(500)

            # Read year options (always in DOM — no need to open dropdown)
            year_opts = attendance_frame.evaluate("""
                () => Array.from(document.querySelectorAll('#WD2C .lsListbox__value'))
                           .map(el => ({
                               id:    el.id,
                               key:   el.getAttribute('data-itemkey') || '',
                               label: el.innerText.trim()
                                          .replace(/^Acad\s*\.\s*Year\s*/i, '')
                                          .trim(),
                           }))
            """)

            # Select the last (most recent) year to trigger semester AJAX
            def _wd_click(eid):
                attendance_frame.evaluate(f"""
                    (function() {{
                        var el = document.getElementById('{eid}');
                        if (!el) return;
                        ['mousedown','mouseup','click'].forEach(function(t) {{
                            el.dispatchEvent(new MouseEvent(t, {{bubbles:true,cancelable:true,view:window}}));
                        }});
                    }})();
                """)

            def _read_sem_opts():
                return attendance_frame.evaluate("""
                    () => {
                        let items = Array.from(
                            document.querySelectorAll('#WD35 .lsListbox__value')
                        );
                        if (items.length > 0)
                            return items.map(el => ({ label: el.innerText.trim() }));
                        // Fallback: any listbox item whose text contains "Semester"
                        items = Array.from(
                            document.querySelectorAll('.lsListbox__value')
                        ).filter(el => /semester/i.test(el.innerText));
                        return items.map(el => ({ label: el.innerText.trim() }));
                    }
                """)

            def _sem_labels():
                return frozenset(s["label"] for s in _read_sem_opts())

            def _wait_for_sem_change(prev_labels, max_iter=40):
                """
                Wait until the semester listbox shows a *different* non-empty set of
                labels compared to prev_labels.  This is the only reliable way to know
                that the AJAX response for the newly selected year has landed —
                simply checking for *any* items returns immediately on stale data.
                """
                for _ in range(max_iter):
                    current = _sem_labels()
                    if current and current != prev_labels:
                        return current
                    attendance_frame.wait_for_timeout(500)
                # Timed out — return whatever is there now
                return _sem_labels()

            # Snapshot whatever semesters the portal shows on initial load
            current_labels = _sem_labels()

            # Collect semesters for every year in one browser session.
            # We iterate oldest → newest and wait for the listbox to *change*
            # after each click, so we never read the previous year's data.
            semesters_by_year: dict[str, list] = {}
            for yr in year_opts:
                _wd_click("WD2B")
                attendance_frame.wait_for_timeout(600)
                _wd_click(yr["id"])
                current_labels = _wait_for_sem_change(current_labels)
                sems = _read_sem_opts()
                semesters_by_year[yr["key"]] = sems
                logger.info("Year %s → %d semesters: %s",
                            yr["label"], len(sems),
                            [s["label"] for s in sems])

            # Use last year's semesters as the current defaults
            sem_opts = semesters_by_year.get(year_opts[-1]["key"], []) if year_opts else []

            default_year = year_opts[-1]["key"] if year_opts else ""
            default_sem  = sem_opts[-1]["label"] if sem_opts else ""

            logger.info(
                "Options fetched for %s***: %d years, semesters=%s",
                sap_id[:4], len(year_opts),
                {k: len(v) for k, v in semesters_by_year.items()},
            )
            return {
                "years":             [{"key": y["key"], "label": y["label"]} for y in year_opts],
                "semesters_by_year": semesters_by_year,
                "semesters":         sem_opts,           # kept for back-compat
                "default_year":      default_year,
                "default_semester":  default_sem,
            }
        finally:
            browser.close()


def fetch_attendance(
    sap_id: str,
    sap_password: str,
    year_key: str = None,
    semester_label: str = None,
    start_date: str = None,
    end_date: str = None,
) -> list[dict]:
    """
    Log into SAP NetWeaver, submit the Detail attendance report, capture
    the generated PDF, and return subject-wise attendance.

    Args:
        sap_id:         Student SAP ID.
        sap_password:   SAP portal password.
        year_key:       Academic year key (e.g. "2025"). Defaults to most recent.
        semester_label: Semester label (e.g. "Semester VI"). Defaults to last.
        start_date:     Report start date in DD.MM.YYYY format. Defaults to _AY_START_DATE.
        end_date:       Report end date in DD.MM.YYYY format. Defaults to today (IST).

    Returns:
        list of {"subject": str, "attended": int, "total": int, "percentage": float},
        sorted by subject name.

    Raises:
        RuntimeError: on login failure, missing portal URL, or outside access window.
                      Do NOT retry — account lockout risk.
    """
    if not SAP_PORTAL_URL:
        raise RuntimeError(
            "SAP_PORTAL_URL is not configured. "
            "Add SAP_PORTAL_URL to your .env file and restart the server."
        )

    _check_portal_window()

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
            attendance_frame = _fill_attendance_form(
                page,
                year_key=year_key,
                semester_label=semester_label,
                start_date=start_date,
                end_date=end_date,
            )

            # ── Submit ────────────────────────────────────────────────────
            # WD52 is the submit button in 3rd-year form layouts; the ID shifts
            # for students with fewer year options.  Find it dynamically by text.
            submit_id = attendance_frame.evaluate("""
                () => {
                    // WD52 for 3-year students (known stable); shifts to WD51 for 2-year, etc.
                    if (document.getElementById('WD52')) return 'WD52';
                    // SAP WD submit button is a div[ct='B'] (NOT input[ct='B']) —
                    // confirmed via DOM inspection: <div ct="B" lsevents='ClientAction:submit'>
                    const btns = Array.from(document.querySelectorAll("[ct='B']"))
                                      .filter(el => el.id && el.id.startsWith('WD'));
                    if (btns.length > 0) return btns[btns.length - 1].id;
                    return null;
                }
            """)
            logger.info("Submit button id=%s", submit_id)
            if not submit_id:
                raise RuntimeError(
                    "Submit button not found in the attendance form. "
                    "The portal layout may have changed — please try again."
                )
            attendance_frame.evaluate(f"""
                (function() {{
                    var el = document.getElementById('{submit_id}');
                    if (!el) return;
                    ['mousedown','mouseup','click'].forEach(function(t) {{
                        el.dispatchEvent(
                            new MouseEvent(t, {{bubbles:true, cancelable:true, view:window}})
                        );
                    }});
                }})();
            """)
            logger.info("Submit clicked — polling for PDF object in frame DOM...")

            # ── Wait for <object ct="PDF"> to appear (SAP WD AJAX delta, up to 30 s) ──
            # In headless Chromium there is no PDF viewer plugin, so the browser
            # never actually fetches <object type="application/pdf"> content.
            # page.expect_response() therefore never fires in headless mode.
            # Instead we extract the absolute URL from el.data and fetch it
            # ourselves via context.request.get(), which shares session cookies
            # but skips download/navigation semantics (no ERR_ABORTED).
            obj_url = None
            for _ in range(60):  # up to 30 s
                obj_url = attendance_frame.evaluate("""
                    () => {
                        const el = document.querySelector(
                            'object[ct="PDF"], object[type="application/pdf"], embed[type="application/pdf"]'
                        );
                        if (!el) return null;
                        // el.data is the resolved absolute URL; getAttribute('data') is raw/relative
                        return el.data || el.src || null;
                    }
                """)
                if obj_url:
                    break
                page.wait_for_timeout(500)

            if not obj_url:
                # Diagnostic: capture DOM state and write to /tmp for inspection
                import json as _json, pathlib as _pl
                _diag = {}
                try:
                    _diag["body_text"] = attendance_frame.evaluate(
                        "() => document.body ? document.body.innerText.slice(0, 1200) : '(no body)'"
                    )
                    _diag["embeds"] = attendance_frame.evaluate("""
                        () => Array.from(document.querySelectorAll('object,embed,iframe'))
                                   .map(el => ({
                                       tag:  el.tagName,
                                       id:   el.id,
                                       ct:   el.getAttribute('ct'),
                                       type: el.getAttribute('type'),
                                       data: el.getAttribute('data') || el.getAttribute('src') || ''
                                   }))
                    """)
                    _diag["frames"] = [f.url for f in page.frames]
                    _diag["all_inputs"] = attendance_frame.evaluate("""
                        () => Array.from(document.querySelectorAll('input'))
                                   .filter(el => el.id && el.id.startsWith('WD') && el.type !== 'hidden')
                                   .map(el => ({id: el.id, ct: el.getAttribute('ct'), value: el.value}))
                    """)
                    _out = _pl.Path("/tmp/sap_diag.json")
                    _out.write_text(_json.dumps(_diag, indent=2), encoding="utf-8")
                    logger.warning("POST-SUBMIT DIAGNOSTIC written to %s", _out)
                    logger.warning("body_text: %s", _diag.get("body_text", "")[:400])
                    logger.warning("embeds: %s", _diag.get("embeds"))
                    logger.warning("frames: %s", _diag.get("frames"))
                except Exception as diag_exc:
                    logger.warning("Diagnostic failed: %s", diag_exc)

                raise RuntimeError(
                    "Attendance PDF did not load after form submission. "
                    "The report server may be slow — please try again."
                )

            logger.info("PDF object found in DOM: %s", obj_url[:100])
            pdf_bytes = _fetch_url_bytes(context, obj_url)

            if not pdf_bytes:
                raise RuntimeError(
                    "Attendance PDF could not be read from the portal. "
                    "Please try again later."
                )

            subjects = _parse_pdf_attendance(pdf_bytes)
            subjects = _enrich_with_course_hours(subjects)
            logger.info(
                "Attendance parsed: %d subjects for %s***", len(subjects), sap_id[:4]
            )
            return subjects
        finally:
            browser.close()


def _fetch_url_bytes(context, url: str):
    """
    Fetch *url* using context.request (Playwright's API-level HTTP client).

    This shares the browser session's cookies without triggering page navigation
    or download semantics — so URLs with sap-wd-filedownload=X (Content-Disposition
    attachment) work fine, unlike page.goto() which aborts with ERR_ABORTED.

    Returns the response bytes if the body is a PDF, otherwise None.
    """
    try:
        resp = context.request.get(url, timeout=30_000)
        if resp.ok:
            body = resp.body()
            ct = resp.headers.get("content-type", "")
            if "pdf" in ct.lower() or body[:4] == b"%PDF":
                logger.info("PDF fetched via context.request (%d bytes)", len(body))
                return body
            logger.warning(
                "context.request response is not PDF (ct=%r, first4=%r)", ct, body[:4]
            )
        else:
            logger.warning("context.request returned %d for PDF URL", resp.status)
    except Exception as exc:
        logger.warning("context.request fetch failed: %s", exc)
    return None


def _login(page, sap_id: str, sap_password: str) -> None:
    """
    Log into the SAP NetWeaver portal.

    The login form has a client-side JavaScript CAPTCHA drawn on a <canvas>.
    The CAPTCHA code is stored in a JS variable `code` — we read it directly
    via page.evaluate() without any OCR.

    Raises RuntimeError on failure — do NOT retry to avoid account lockout.
    Credentials are never passed to the logger.
    """
    logger.info("Navigating to SAP portal...")
    # Use "load" so the onload handler fires and Captcha() sets window.code
    page.goto(SAP_PORTAL_URL, wait_until="load", timeout=30_000)

    try:
        page.wait_for_selector("#logonuidfield", timeout=10_000)
    except PlaywrightTimeout:
        raise RuntimeError(
            "SAP login page did not load. "
            "Check SAP_PORTAL_URL in your .env file."
        )

    page.fill("#logonuidfield", sap_id)
    page.fill("#logonpassfield", sap_password)

    # Poll for captcha code — Captcha() runs onload, poll up to 3 s
    try:
        page.wait_for_function(
            "() => typeof window.code === 'string' && window.code.length > 0",
            timeout=3000,
        )
        captcha_code = page.evaluate("() => window.code")
    except Exception:
        captcha_code = ""

    logger.info("CAPTCHA resolved (client-side JS)")
    page.fill("#txtInput", str(captcha_code))
    page.click("#Button1")

    try:
        page.wait_for_load_state("networkidle", timeout=25_000)
    except PlaywrightTimeout:
        pass  # networkidle can be flaky on heavy portals — check content instead

    if page.query_selector("#logonuidfield"):
        raise RuntimeError(
            "SAP login failed — login form still visible after submission. "
            "Check your SAP credentials. Do NOT retry automatically to avoid account lockout."
        )

    logger.info("SAP login successful for %s***", sap_id[:4])


def _fill_attendance_form(
    page,
    year_key: str = None,
    semester_label: str = None,
    start_date: str = None,
    end_date: str = None,
):
    """
    Click 'Attendance Display for Students', fill the Detail Report form,
    and return the attendance WebDynpro frame.  Does NOT click Submit —
    that is done by fetch_attendance() inside page.expect_response().

    Args:
        year_key:       data-itemkey value of the year to select (e.g. "2025").
                        Defaults to the last (most recent) year.
        semester_label: Text label of the semester (e.g. "Semester VI").
                        Defaults to the last semester in the list.
        start_date:     Report start date in DD.MM.YYYY format.
                        Defaults to _AY_START_DATE.
        end_date:       Report end date in DD.MM.YYYY format.
                        Defaults to today (IST).
    """
    try:
        attendance_link = page.wait_for_selector(
            "a:has-text('Attendance Display for Students')",
            timeout=30_000,
        )
    except PlaywrightTimeout:
        raise RuntimeError(
            "Attendance link not found after 30 s. "
            "The portal navigation may still be loading — please try again."
        )

    attendance_link.click()
    logger.info("Clicked 'Attendance Display for Students', waiting for iView...")

    # Wait for the WebDynpro frame (up to 30 s)
    attendance_frame = None
    for _ in range(60):
        for frame in page.frames:
            if "ZSVKM_STUDENT_ATTENDANCE2" in frame.url:
                attendance_frame = frame
                break
        if attendance_frame:
            break
        page.wait_for_timeout(500)

    if not attendance_frame:
        raise RuntimeError(
            "Attendance WebDynpro frame did not load within 30 seconds. "
            "The portal may be overloaded — try again during off-peak hours."
        )

    logger.info("Attendance frame found: %s", attendance_frame.url[:80])

    try:
        attendance_frame.wait_for_selector("#WD2B", timeout=30_000)
    except PlaywrightTimeout:
        raise RuntimeError(
            "Attendance form did not render within 30 seconds. "
            "The portal may be loading slowly — please try again."
        )

    attendance_frame.wait_for_timeout(1000)

    def _wd_click(eid: str) -> None:
        attendance_frame.evaluate(f"""
            (function() {{
                var el = document.getElementById('{eid}');
                if (!el) return;
                ['mousedown', 'mouseup', 'click'].forEach(function(t) {{
                    el.dispatchEvent(
                        new MouseEvent(t, {{bubbles: true, cancelable: true, view: window}})
                    );
                }});
            }})();
        """)

    def _read_sem_opts():
        return attendance_frame.evaluate("""
            () => {
                let items = Array.from(
                    document.querySelectorAll('#WD35 .lsListbox__value')
                );
                if (items.length > 0)
                    return items.map(el => ({
                        id:    el.id,
                        label: el.innerText.trim(),
                        key:   el.getAttribute('data-itemkey') || ''
                    }));
                items = Array.from(
                    document.querySelectorAll('.lsListbox__value')
                ).filter(el => /semester/i.test(el.innerText));
                return items.map(el => ({
                    id:    el.id,
                    label: el.innerText.trim(),
                    key:   el.getAttribute('data-itemkey') || ''
                }));
            }
        """)

    def _sem_labels():
        return frozenset(s["label"] for s in _read_sem_opts())

    def _wait_for_sem_change(prev_labels, max_iter=40):
        """Wait until the semester listbox shows a different non-empty set of labels."""
        for _ in range(max_iter):
            current = _sem_labels()
            if current and current != prev_labels:
                return current
            attendance_frame.wait_for_timeout(500)
        return _sem_labels()

    # Snapshot semester labels BEFORE selecting a year so we can detect the AJAX change
    current_labels = _sem_labels()

    # ── Select Academic Year ──────────────────────────────────────
    _wd_click("WD2B")
    attendance_frame.wait_for_timeout(800)

    if year_key:
        # Find item by data-itemkey attribute
        yr_id = attendance_frame.evaluate(f"""
            () => {{
                var el = document.querySelector('#WD2C [data-itemkey="{year_key}"]');
                return el ? el.id : null;
            }}
        """)
        if yr_id:
            _wd_click(yr_id)
            logger.info("Selected year key=%s (id=%s)", year_key, yr_id)
        else:
            # Fall back to last item if key not found
            yr_id = attendance_frame.evaluate("""
                () => { var items = document.querySelectorAll('#WD2C .lsListbox__value');
                        return items.length ? items[items.length-1].id : null; }
            """)
            if yr_id:
                _wd_click(yr_id)
                logger.info("Year key=%s not found; selected last year id=%s", year_key, yr_id)
    else:
        yr_id = attendance_frame.evaluate("""
            () => { var items = document.querySelectorAll('#WD2C .lsListbox__value');
                    return items.length ? items[items.length-1].id : null; }
        """)
        if yr_id:
            _wd_click(yr_id)
            logger.info("Selected last year id=%s", yr_id)

    # ── Wait for Semester listbox to change (not just exist) ─────
    # The portal pre-populates the listbox on initial load; checking for
    # `has_items > 0` returns immediately with stale data for students who
    # already have semester items in the DOM.  We must wait for the labels
    # to actually change after the year-selection AJAX resolves.
    current_labels = _wait_for_sem_change(current_labels)
    if not current_labels:
        raise RuntimeError(
            "Semester dropdown did not populate after selecting Academic Year. "
            "The portal backend is slow — please try again later."
        )
    logger.info("Semester listbox updated: %s", sorted(current_labels))

    # ── Select Semester via direct AJAX POST ─────────────────────
    # Semester listbox items are injected into the DOM via an AJAX delta
    # after year selection.  Clicking them updates the visual display but
    # does NOT fire a ComboBox_Select event to the SAP server — broken
    # event delegation for dynamically-added items in SAP WebDynpro.
    #
    # Fix: POST the ComboBox_Select AJAX request directly (same format as
    # the year-item click), then eval() the JS delta response so SAP's
    # client state (including the refreshed sap-wd-secure-id) is applied
    # to the DOM before the next interaction.

    sem_opts = _read_sem_opts()
    if not sem_opts:
        raise RuntimeError(
            "Semester options not found after year selection. "
            "The portal backend is slow — please try again later."
        )

    # Pick the target semester
    if semester_label:
        target_sem = next((s for s in sem_opts if s["label"] == semester_label), None)
        if not target_sem:
            logger.warning(
                "Semester label %r not found in %s; using last",
                semester_label, [s["label"] for s in sem_opts],
            )
            target_sem = sem_opts[-1]
    else:
        target_sem = sem_opts[-1]

    logger.info(
        "Target semester: label=%r key=%r id=%r",
        target_sem["label"], target_sem["key"], target_sem["id"],
    )

    # Semester combobox ID: the 2nd input[ct='CB'] (year is 1st)
    sem_cb_id = attendance_frame.evaluate("""
        () => {
            const cbs = Array.from(document.querySelectorAll("input[ct='CB']"))
                             .filter(el => el.id && el.id.startsWith('WD'));
            return cbs.length >= 2 ? cbs[1].id : (cbs.length ? cbs[0].id : 'WD33');
        }
    """)
    logger.info("Semester combobox id: %s", sem_cb_id)

    # Capture form params needed for the AJAX POST
    form_params = attendance_frame.evaluate("""
        () => {
            const s = document.querySelector('input[name="sap-wd-secure-id"]');
            const a = document.querySelector('input[name="fesrAppName"]');
            return {
                secureId: s ? s.value : '',
                appName:  a ? a.value : 'ZSVKM_STUDENT_ATTENDANCE2',
                frameUrl: window.location.href
            };
        }
    """)

    sem_key = target_sem.get("key", "")
    if sem_key and form_params.get("secureId") and form_params.get("frameUrl"):
        # POST ComboBox_Select directly — same encoding SAP uses for year selection
        ajax_result = attendance_frame.evaluate(f"""
            async () => {{
                const semCbId  = {repr(sem_cb_id)};
                const semKey   = {repr(sem_key)};
                const secureId = {repr(form_params['secureId'])};
                const appName  = {repr(form_params.get('appName', 'ZSVKM_STUDENT_ATTENDANCE2'))};
                const frameUrl = {repr(form_params['frameUrl'])};

                const evt = (
                    'ComboBox_Select~E002Id~E004' + semCbId +
                    '~E005Key~E004' + semKey +
                    '~E005ByEnter~E004false~E003' +
                    '~E002ResponseData~E004delta~E005ClientAction~E004submit~E003~E002~E003'
                );
                const body = (
                    'sap-charset=utf-8' +
                    '&sap-wd-secure-id=' + encodeURIComponent(secureId) +
                    '&fesrAppName='      + encodeURIComponent(appName) +
                    '&SAPEVENTQUEUE='    + encodeURIComponent(evt)
                );

                try {{
                    const resp = await fetch(frameUrl, {{
                        method:      'POST',
                        headers:     {{'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}},
                        body:        body,
                        credentials: 'include',
                    }});
                    const ct   = resp.headers.get('content-type') || '';
                    const text = await resp.text();

                    // SAP WD delta responses are JavaScript — executing them
                    // applies DOM updates AND refreshes sap-wd-secure-id in place.
                    if (ct.includes('javascript') || ct.includes('text/html')) {{
                        try {{ eval(text); }} catch (_) {{}}
                    }}

                    return {{
                        ok:      resp.ok,
                        status:  resp.status,
                        ct:      ct,
                        len:     text.length,
                        preview: text.slice(0, 300),
                    }};
                }} catch (e) {{
                    return {{ ok: false, error: String(e) }};
                }}
            }}
        """)
        logger.info(
            "Semester AJAX POST: ok=%s status=%s len=%s preview=%r",
            ajax_result.get("ok"), ajax_result.get("status"),
            ajax_result.get("len"), ajax_result.get("preview", "")[:120],
        )
    else:
        # Fallback: no data-itemkey — click the item and hope for the best
        logger.warning(
            "No data-itemkey for semester item id=%s — falling back to click",
            target_sem.get("id"),
        )
        if target_sem.get("id"):
            _wd_click(target_sem["id"])

    logger.info("Selected semester label=%s", target_sem["label"])
    # Wait for SAP WD delta to settle — may shift report-type IDs
    attendance_frame.wait_for_timeout(2000)

    # ── Select Detail Report ──────────────────────────────────────
    # The report-type combobox trigger ID shifts with the number of year options
    # (WD3A for 3rd-year, WD39 for 2nd-year, etc.).  Find it dynamically as the
    # last ct=CB input in the form — year and semester comboboxes precede it.
    report_trigger_id = attendance_frame.evaluate("""
        () => {
            const boxes = Array.from(document.querySelectorAll("input[ct='CB']"))
                               .filter(el => el.id && el.id.startsWith('WD'));
            return boxes.length > 0 ? boxes[boxes.length - 1].id : 'WD3A';
        }
    """)
    logger.info("Report-type combobox trigger: %s", report_trigger_id)
    _wd_click(report_trigger_id)
    attendance_frame.wait_for_timeout(800)

    detail_info = attendance_frame.evaluate("""
        () => {
            for (const el of document.querySelectorAll('.lsListbox__value')) {
                if (/detail/i.test(el.innerText))
                    return { id: el.id, text: el.innerText.trim() };
            }
            return { id: 'WD3D', text: '(fallback)' };
        }
    """)
    _wd_click(detail_info["id"])
    logger.info("Selected Detail Report (id=%s text=%r)", detail_info["id"], detail_info["text"])
    attendance_frame.wait_for_timeout(2000)

    # Diagnostic: log all WD inputs currently in the form to understand what rendered
    all_inputs = attendance_frame.evaluate("""
        () => Array.from(document.querySelectorAll('input'))
                   .filter(el => el.id && el.id.startsWith('WD') && el.type !== 'hidden')
                   .map(el => ({ id: el.id, type: el.type, ct: el.getAttribute('ct'), visible: el.offsetParent !== null }))
    """)
    logger.info("Inputs in form after Detail Report: %s", all_inputs)

    # ── Fill date range ───────────────────────────────────────────
    resolved_start = start_date or _AY_START_DATE
    resolved_end   = end_date   or datetime.now(_IST).strftime("%d.%m.%Y")

    date_input_ids = []
    for _ in range(30):   # up to 15 s — form AJAX after Detail selection can be slow
        date_input_ids = attendance_frame.evaluate("""
            () => {
                // Primary: SAP date inputs with ct='I'
                let ids = Array.from(document.querySelectorAll("input[ct='I']"))
                               .filter(el => el.id && el.id.startsWith('WD') && el.type !== 'hidden')
                               .map(el => el.id);
                if (ids.length >= 2) return ids;
                // Fallback: any visible text input with a WD id
                ids = Array.from(document.querySelectorAll("input[type='text']"))
                           .filter(el => el.id && el.id.startsWith('WD') && el.offsetParent !== null)
                           .map(el => el.id);
                return ids;
            }
        """)
        if len(date_input_ids) >= 2:
            break
        attendance_frame.wait_for_timeout(500)

    if len(date_input_ids) >= 2:
        start_id, end_id = date_input_ids[0], date_input_ids[1]
        attendance_frame.fill(f"#{start_id}", resolved_start)
        attendance_frame.fill(f"#{end_id}", resolved_end)
        attendance_frame.evaluate(f"""
            (function() {{
                ['{start_id}', '{end_id}'].forEach(function(id) {{
                    var el = document.getElementById(id);
                    if (!el) return;
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    el.dispatchEvent(new Event('blur',   {{bubbles: true}}));
                }});
            }})();
        """)
        logger.info(
            "Filled date range %s → %s (fields: %s, %s)",
            resolved_start, resolved_end, start_id, end_id,
        )
        attendance_frame.wait_for_timeout(500)
    else:
        logger.warning(
            "Date inputs not found after Detail selection (%d ct='I' WD inputs).",
            len(date_input_ids),
        )

    # Submit is handled by fetch_attendance() after this function returns.
    return attendance_frame


# Matches elective category prefixes in attendance names: "OE-III ", "DE-II ", etc.
_ELECTIVE_PFX_RE = re.compile(r"^[A-Z]{1,4}-\s*(?:[IVX]+|\d+)\s+", re.IGNORECASE)


def _normalize(name: str) -> str:
    """Strip elective prefix, lowercase, replace non-alphanumeric with space."""
    name = _ELECTIVE_PFX_RE.sub("", name)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", name.lower())).strip()


def _enrich_with_course_hours(subjects: list[dict]) -> list[dict]:
    """
    Load course_durations.json and add two computed fields to each subject:

        pending    = course_total_hours − total_conducted
                     (lectures not yet held this semester; None if course not matched)

        to_attend  = ceil(0.80 × course_total_hours) − attended
                     (additional lectures needed to reach 80%; clamped to 0 if already met)

    Course names are matched using normalised string comparison with a token-overlap
    fallback (≥ 60 % overlap required) — handles hyphen-vs-space variants and minor
    truncations from the PDF.
    """
    if not COURSE_DURATIONS_PATH.exists():
        logger.warning("course_durations.json not found — skipping pending/to_attend enrichment")
        for s in subjects:
            s["pending"] = None
            s["to_attend"] = None
        return subjects

    with open(COURSE_DURATIONS_PATH, encoding="utf-8") as f:
        durations = json.load(f)

    # Build normalised-name → total_hours lookup (JSON file = base data)
    dur_map: dict[str, int] = {_normalize(d["course"]): d["total_hours"] for d in durations}

    # Overlay user-submitted hours from Supabase (survives redeployment)
    try:
        from backend.config import SUPABASE_KEY, SUPABASE_URL
        if SUPABASE_URL and SUPABASE_KEY:
            import urllib.request
            req = urllib.request.Request(
                f"{SUPABASE_URL}/rest/v1/course_hours?select=course,total_hours",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                rows = json.loads(resp.read())
            for row in rows:
                dur_map[_normalize(row["course"])] = row["total_hours"]
            logger.info("Loaded %d user-submitted course hours from Supabase", len(rows))
    except Exception as exc:
        logger.debug("Could not load user course hours from Supabase: %s", exc)

    def _best_match(subject_name: str):
        norm = _normalize(subject_name)

        # 1. Exact match
        if norm in dur_map:
            return dur_map[norm]

        # 2. One is a substring of the other — only when lengths are close
        # (ratio ≥ 0.6) to avoid "physics" matching "quantum physics" or
        # "mathematics" matching "applied engineering mathematics".
        for key, hours in dur_map.items():
            if norm in key or key in norm:
                ratio = min(len(norm), len(key)) / max(len(norm), len(key))
                if ratio >= 0.6:
                    return hours

        # 3. Token-prefix match — each token pair must be mutual prefixes and
        #    both tokens must be ≥ 3 chars (prevents "e" matching "entrepreneurship")
        norm_tokens = norm.split()
        for key, hours in dur_map.items():
            key_tokens = key.split()
            short, long_ = (
                (norm_tokens, key_tokens) if len(norm_tokens) <= len(key_tokens)
                else (key_tokens, norm_tokens)
            )
            if not short:
                continue
            if all(
                (l.startswith(s) or s.startswith(l)) and min(len(s), len(l)) >= 3
                for s, l in zip(short, long_)
            ):
                return hours

        # 4. Token-overlap score ≥ 0.60
        tokens = set(norm.split())
        best_score, best_hours = 0.0, None
        for key, hours in dur_map.items():
            key_tokens = set(key.split())
            if not key_tokens:
                continue
            overlap = len(tokens & key_tokens) / max(len(tokens), len(key_tokens))
            if overlap > best_score and overlap >= 0.60:
                best_score = overlap
                best_hours = hours

        return best_hours

    for s in subjects:
        course_hrs = _best_match(s["subject"])
        if course_hrs is None:
            s["pending"]   = None
            s["to_attend"] = None
        else:
            s["pending"]   = max(0, course_hrs - s["total"])
            s["to_attend"] = max(0, math.ceil(0.80 * course_hrs) - s["attended"])

    return subjects


def _parse_pdf_attendance(pdf_bytes: bytes) -> list[dict]:
    """
    Parse the SAP attendance PDF and compute subject-wise attendance.

    PDF row structure (6 consecutive lines per lecture):
        Sr No  |  Course Name  |  Date  |  Start Time  |  End Time  |  Status

    Course names carry a class-section suffix (e.g. "Machine Learning T2 MBA Tech CE A1").
    The suffix is stripped with a regex, and names are grouped by their first 12 characters
    to merge truncation variants (e.g. "Distributed Compu" / "Distributed Computing").

    Status codes:
        P  = Present  → present
        E  = Exemption → present
        L  = Late      → present
        A  = Absent    → absent
        NU = Not Updated → skipped

    Returns:
        list of {"subject": str, "percentage": float}, sorted by subject name.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    lines: list[str] = []
    for pg in doc:
        lines.extend(pg.get_text().split("\n"))

    _sr_re = re.compile(r"^\d+$")
    records: list[tuple[str, str, str]] = []   # (course, status, date_str)
    i = 0
    while i < len(lines) - 5:
        s0 = lines[i].strip()
        s2 = lines[i + 2].strip()
        s5 = lines[i + 5].strip()
        if _sr_re.match(s0) and _MONTH_RE.match(s2) and s5 in _VALID_STATUSES:
            records.append((lines[i + 1].strip(), s5, s2))
            i += 6
        else:
            i += 1

    if not records:
        logger.warning("No attendance rows found in PDF — check portal structure")
        return []

    logger.info("Parsed %d raw attendance rows from PDF", len(records))

    _suffix_re = re.compile(r"\s*[TP]\d+.*$")
    # Strip elective/department category prefixes: "OE-III ", "DE-II ", "PE-I ", etc.
    _elective_pfx_re = re.compile(r"^[A-Z]{1,4}-\s*(?:[IVX]+|\d+)\s+", re.IGNORECASE)

    def clean_name(raw: str) -> str:
        name = _elective_pfx_re.sub("", raw)   # strip "OE-III ", "DE-II " …
        name = _suffix_re.sub("", name)         # strip "T2 MBA Tech CE A1" …
        return name.strip()

    _STOP_WORDS = {"of", "for", "to", "in", "and", "the", "with", "a", "an",
                   "by", "at", "into", "on", "from"}

    def course_key(name: str) -> str:
        """
        Grouping key that merges truncated PDF variants of the same course.

        Uses the first two *meaningful* words (stop-words skipped) so that:
          • "Human Comp Inter" and "Human Computer Interaction" → "human_comp"
          • "Elements of Automation" → "elements_auto"
          • "Elements of Project Management" → "elements_proj"
        Stop-word skipping prevents "of"/"for"/"to" from anchoring the key
        and causing false merges between distinct courses.
        """
        words = [w for w in name.lower().split() if w not in _STOP_WORDS]
        if not words:
            return name.lower()
        key = words[0]
        if len(words) > 1:
            key += "_" + words[1][:4]
        return key

    # Group by course key; keep longest display name
    counts: dict[str, dict] = defaultdict(
        lambda: {"present": 0, "total": 0, "not_updated": 0, "display": "", "last_dt": None, "last_str": ""}
    )

    _date_re = re.compile(r"^(\w+)\s+(\d+),\s+(\d{4})$")

    def _parse_date(date_str: str):
        """Parse 'Jan 2, 2026' → datetime, return None on failure."""
        m = _date_re.match(date_str)
        if not m:
            return None
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y")
        except ValueError:
            return None

    for course, status, date_str in records:
        cleaned = clean_name(course)
        if not cleaned:
            continue
        key = course_key(cleaned)
        c = counts[key]
        if len(cleaned) > len(c["display"]):
            c["display"] = cleaned
        # Track latest date for this subject
        dt = _parse_date(date_str)
        if dt and (c["last_dt"] is None or dt > c["last_dt"]):
            c["last_dt"] = dt
            c["last_str"] = dt.strftime("%-d %b %Y")   # e.g. "27 Mar 2026"
        if status == "NU":
            c["not_updated"] += 1
        else:
            c["total"] += 1
            if status in _PRESENT_STATUSES:
                c["present"] += 1

    subjects = []
    for c in sorted(counts.values(), key=lambda x: x["display"]):
        if c["total"] > 0:
            pct = round(c["present"] / c["total"] * 100, 1)
            subjects.append({
                "subject":     c["display"],
                "attended":    c["present"],
                "total":       c["total"],
                "not_updated": c["not_updated"],
                "percentage":  pct,
                "last_entry":  c["last_str"],
            })
        elif c["not_updated"] > 0:
            subjects.append({
                "subject":     c["display"],
                "attended":    0,
                "total":       0,
                "not_updated": c["not_updated"],
                "percentage":  None,
                "last_entry":  c["last_str"],
            })

    return subjects
