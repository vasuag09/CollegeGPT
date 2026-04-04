"""
backend/attendance_service.py

NM-GPT Attendance Service: Queue-Based Playwright Architecture.
Handles 100+ concurrent users within 512MB RAM.

Implementation:
- Restores robust WebDynpro interaction logic from historical git commits.
- Handles Year, Semester, and Detailed Report selection.
- Correctly fills From/To date fields.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import hashlib
import difflib
import re
import time
import urllib.request
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF
from fastapi import APIRouter, FastAPI, HTTPException
from playwright.async_api import (
    Browser,
    async_playwright,
    TimeoutError as PlaywrightTimeout,
)
from pydantic import BaseModel

from backend.config import COURSE_DURATIONS_PATH, SUPABASE_KEY, SUPABASE_URL

logger = logging.getLogger("nmgpt.attendance")

# Configuration
SAP_PORTAL_URL = "https://sdc-sppap1.svkm.ac.in:50001/irj/portal"
CACHE_TTL_SECONDS = 10 * 60
MAX_CACHE_ENTRIES = 300
MAX_QUEUE_SIZE = 40
SCRAPE_TIMEOUT_SECONDS = 150

# Concurrency limits
_scrape_semaphore = asyncio.Semaphore(1)

# IST Timezone
_IST = timezone(timedelta(hours=5, minutes=30))
_PORTAL_OPEN_HOUR = 18
_PORTAL_CLOSE_HOUR = 7

_PRESENT_STATUSES = {"P", "E", "L"}
_VALID_STATUSES = {"P", "A", "E", "L", "NU"}
_MONTH_RE = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d")
_ELECTIVE_PFX_RE = re.compile(r"^[A-Z]{1,4}-\s*(?:[IVX]+|\d+)\s+", re.IGNORECASE)
_SECTION_RE = re.compile(r"([TP])\d+", re.IGNORECASE)
_CUT_HINTS = (" mba", " div", " batch", " all")
_NOISE_TOKENS = {
    "mba",
    "tech",
    "ce",
    "div",
    "batch",
    "all",
    "de",
    "iii",
    "ii",
    "iv",
    "vi",
    "v",
    "a",
    "b",
    "c",
}

# ---------------------------------------------------------------------------
# 1. State
# ---------------------------------------------------------------------------


class State:
    pw_instance: Any = None
    browser: Optional[Browser] = None
    launch_lock = asyncio.Lock()


_state = State()

# ---------------------------------------------------------------------------
# 2. Models
# ---------------------------------------------------------------------------


class AttendanceRequest(BaseModel):
    sap_id: str
    password: str
    year_key: Optional[str] = None
    semester_label: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class AttendanceOptionsRequest(BaseModel):
    sap_id: str
    sap_password: str


class AttendanceResponse(BaseModel):
    status: str
    data: Optional[Any] = None
    queue_position: Optional[int] = None


# Cache & Tracker
@dataclass
class _CacheEntry:
    data: Any
    expires_at: float


class _TTLCache:
    def __init__(self, ttl: float = CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._store: Dict[str, _CacheEntry] = {}

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now > v.expires_at]
        for key in expired:
            del self._store[key]

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry or time.monotonic() > entry.expires_at:
            if entry:
                del self._store[key]
            return None
        return entry.data

    def set(self, key: str, data: Any) -> None:
        self._purge_expired()
        if len(self._store) >= MAX_CACHE_ENTRIES:
            oldest_key = min(self._store.items(), key=lambda item: item[1].expires_at)[
                0
            ]
            del self._store[oldest_key]
        self._store[key] = _CacheEntry(
            data=data, expires_at=time.monotonic() + self._ttl
        )

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class _JobTracker:
    def __init__(self) -> None:
        self._queued: set[str] = set()
        self._processing: set[str] = set()

    def is_queued(self, sid: str) -> bool:
        return sid in self._queued

    def is_processing(self, sid: str) -> bool:
        return sid in self._processing

    def mark_queued(self, sid: str):
        self._queued.add(sid)

    def mark_processing(self, sid: str):
        self._queued.discard(sid)
        self._processing.add(sid)

    def mark_done(self, sid: str):
        self._queued.discard(sid)
        self._processing.discard(sid)

    @property
    def depth(self) -> int:
        return len(self._queued)


_cache = _TTLCache()
_tracker = _JobTracker()
_queue: asyncio.Queue[tuple[str, str, dict, str, str]] = asyncio.Queue(
    maxsize=MAX_QUEUE_SIZE
)

# ---------------------------------------------------------------------------
# 3. Browser Management
# ---------------------------------------------------------------------------


async def get_browser() -> Browser:
    async with _state.launch_lock:
        if _state.browser is None or not _state.browser.is_connected():
            if _state.browser:
                try:
                    await _state.browser.close()
                except:
                    pass

            logger.info("Initializing/restarting singleton browser instance...")
            _state.browser = await _state.pw_instance.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--no-first-run",
                    "--mute-audio",
                ],
            )
        return _state.browser


# ---------------------------------------------------------------------------
# 4. Scraper Impl
# ---------------------------------------------------------------------------


async def _wd_click(frame: Any, eid: str) -> None:
    await frame.evaluate(f"""
        (function() {{
            var el = document.getElementById('{eid}');
            if (!el) return;
            ['mousedown','mouseup','click'].forEach(function(t) {{
                el.dispatchEvent(new MouseEvent(t, {{bubbles:true, cancelable:true, view:window}}));
            }});
        }})();
    """)


async def _scrape_logic(sap_id: str, password: str, params: dict, job_type: str) -> Any:
    browser = await get_browser()
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
    )
    page = await context.new_page()
    page.set_default_timeout(30000)
    try:
        now_ist = datetime.now(_IST)
        if _PORTAL_CLOSE_HOUR <= now_ist.hour < _PORTAL_OPEN_HOUR:
            raise RuntimeError("SAP portal is closed (Access window: 6 PM - 7 AM IST).")

        # 1. Login
        logger.info("[%s] portal logic: nav to portal...", sap_id)
        await page.goto(SAP_PORTAL_URL, wait_until="load", timeout=30000)
        await page.fill("#logonuidfield", sap_id)
        await page.fill("#logonpassfield", password)
        await page.wait_for_function(
            "() => typeof window.code === 'string' && window.code.length > 0",
            timeout=12000,
        )
        captcha_code = await page.evaluate("() => window.code")
        await page.fill("#txtInput", str(captcha_code))
        await page.click("#Button1")

        await asyncio.sleep(4)
        if await page.query_selector("#logonForm"):
            raise RuntimeError("Invalid credentials")

        # 2. Select Attendance Link
        # Wait for portal nav to finish rendering (SAP portal uses JS-rendered navigation)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            pass  # proceed anyway if portal never fully settles

        selectors = [
            "a:has-text('Attendance Display')",
            "a:has-text('Attendance Display for Students')",
            "a:has-text('Student Attendance')",
        ]
        link = None
        # Search main page first, then all child frames
        # (SAP portal nav is often rendered inside a portal navigation iframe)
        all_frames = [page.main_frame] + [
            f for f in page.frames if f != page.main_frame
        ]
        for frame in all_frames:
            for sel in selectors:
                try:
                    el = await frame.query_selector(sel)
                    if el:
                        link = el
                        break
                except Exception:
                    pass
            if link:
                break

        if not link:
            raise RuntimeError("Attendance Display link not found on dashboard.")

        await link.click()

        # 3. Handle iView Frame
        attendance_frame = None
        for _ in range(40):
            for f in page.frames:
                if "ZSVKM_STUDENT_ATTENDANCE2" in f.url:
                    attendance_frame = f
                    break
            if attendance_frame:
                break
            await asyncio.sleep(0.5)

        if not attendance_frame:
            raise RuntimeError("Attendance iView frame failed to load.")

        await attendance_frame.wait_for_load_state("domcontentloaded")
        await attendance_frame.wait_for_function(
            """
            () => {
                const hasKnownYear = !!document.getElementById('WD2B');
                const hasAnyCombo = !!document.querySelector("input[ct='CB'][id^='WD']");
                return hasKnownYear || hasAnyCombo;
            }
            """,
            timeout=45000,
        )

        if job_type == "options":
            return await _extract_options(attendance_frame)
        else:
            return await _extract_attendance_pdf(page, attendance_frame, params)
    finally:
        await context.close()


async def _wd_sem_labels(frame: Any) -> frozenset:
    """Return frozenset of current semester listbox labels (WD35 container first, fallback)."""
    items = await frame.evaluate("""
        () => {
            let items = Array.from(document.querySelectorAll('#WD35 .lsListbox__value'));
            if (items.length > 0) return items.map(el => el.innerText.trim());
            return Array.from(document.querySelectorAll('.lsListbox__value'))
                        .filter(el => /semester/i.test(el.innerText))
                        .map(el => el.innerText.trim());
        }
    """)
    return frozenset(items or [])


async def _wd_wait_for_sem_change(
    frame: Any, prev_labels: frozenset, max_iter: int = 40
) -> frozenset:
    """Wait until semester listbox shows a different non-empty set of labels."""
    for _ in range(max_iter):
        current = await _wd_sem_labels(frame)
        if current and current != prev_labels:
            return current
        await asyncio.sleep(0.5)
    return await _wd_sem_labels(frame)


async def _extract_options(frame: Any) -> dict:
    # 1. Year dropdown: always WD2B in ZSVKM_STUDENT_ATTENDANCE2, with generic fallback
    year_trigger = await frame.evaluate("""
        () => document.getElementById('WD2B')
            ? 'WD2B'
            : ((document.querySelector("input[ct='CB'][id^='WD']") || {}).id || null)
    """)
    if not year_trigger:
        raise RuntimeError("Academic year dropdown not found in attendance form.")

    await _wd_click(frame, year_trigger)
    await asyncio.sleep(0.8)

    # Year options live in #WD2C container
    year_opts = await frame.evaluate(r"""
        () => {
            let items = Array.from(document.querySelectorAll('#WD2C .lsListbox__value'));
            if (items.length === 0)
                items = Array.from(document.querySelectorAll('.lsListbox__value'))
                             .filter(el => /202\d/i.test(el.innerText));
            return items.map(el => ({
                id:    el.id,
                key:   el.getAttribute('data-itemkey') || '',
                label: el.innerText.trim().replace(/^Acad\s*\.\s*Year\s*/i, '').trim(),
            }));
        }
    """)
    if not year_opts:
        raise RuntimeError("Failed to extract academic year options.")

    # Snapshot current semester labels before clicking year
    prev_labels = await _wd_sem_labels(frame)

    # 2. Select latest year to trigger Semester AJAX
    latest_year = year_opts[-1]
    await _wd_click(frame, latest_year["id"])
    logger.info(
        "[options] Selected year id=%s key=%s", latest_year["id"], latest_year["key"]
    )

    # Wait for semester labels to actually change (not just a fixed sleep)
    current_labels = await _wd_wait_for_sem_change(frame, prev_labels)
    logger.info(
        "[options] Semester labels after year select: %s", sorted(current_labels)
    )

    # 3. Read semester options from WD35 container
    sem_opts = await frame.evaluate("""
        () => {
            let items = Array.from(document.querySelectorAll('#WD35 .lsListbox__value'));
            if (items.length > 0) return items.map(el => ({ label: el.innerText.trim() }));
            return Array.from(document.querySelectorAll('.lsListbox__value'))
                        .filter(el => /semester/i.test(el.innerText))
                        .map(el => ({ label: el.innerText.trim() }));
        }
    """)

    # De-dupe
    seen: set = set()
    final_sems = []
    for s in sem_opts:
        if s["label"] not in seen:
            final_sems.append(s)
            seen.add(s["label"])

    return {
        "years": year_opts,
        "semesters_by_year": {yr["key"]: final_sems for yr in year_opts},
        "default_year": year_opts[-1]["key"],
        "default_semester": final_sems[-1]["label"] if final_sems else "",
    }


async def _extract_attendance_pdf(page: Any, frame: Any, params: dict) -> list[dict]:
    safe_params = {k: ("***" if k == "password" else v) for k, v in params.items()}
    logger.info("PDF extraction start: params=%s", safe_params)

    # ── 1. Academic Year ──────────────────────────────────────────────────────
    # Year dropdown is always WD2B in ZSVKM_STUDENT_ATTENDANCE2; fall back to
    # first ct=CB input if layout shifts.
    year_trigger = await frame.evaluate("""
        () => document.getElementById('WD2B')
            ? 'WD2B'
            : ((document.querySelector("input[ct='CB'][id^='WD']") || {}).id || null)
    """)
    if not year_trigger:
        raise RuntimeError("Academic year dropdown trigger not found.")

    # Snapshot current semester labels BEFORE year selection so we can detect change
    prev_sem_labels = await _wd_sem_labels(frame)

    await _wd_click(frame, year_trigger)
    await asyncio.sleep(0.8)

    year_target = params.get("year_key") or "2025"
    # Year items live in #WD2C container; fall back to global search
    year_id = await frame.evaluate(f"""
        () => {{
            let el = document.querySelector('#WD2C [data-itemkey="{year_target}"]');
            if (el) return el.id;
            el = Array.from(document.querySelectorAll('.lsListbox__value'))
                      .find(e => e.getAttribute('data-itemkey') === '{year_target}');
            return el ? el.id : null;
        }}
    """)
    if year_id:
        await _wd_click(frame, year_id)
        logger.info(
            "[%s] Year key=%s selected (id=%s)",
            params.get("sap_id", "?"),
            year_target,
            year_id,
        )
    else:
        # Fall back to last item
        fallback_id = await frame.evaluate("""
            () => { const items = document.querySelectorAll('#WD2C .lsListbox__value');
                    return items.length ? items[items.length-1].id : null; }
        """)
        if fallback_id:
            await _wd_click(frame, fallback_id)
            logger.warning(
                "[%s] Year key=%s not found; selected last year id=%s",
                params.get("sap_id", "?"),
                year_target,
                fallback_id,
            )

    # Wait for semester listbox to actually change (not just a fixed sleep)
    await _wd_wait_for_sem_change(frame, prev_sem_labels)
    current_sem_labels = await _wd_sem_labels(frame)
    logger.info(
        "[%s] Semester labels after year select: %s",
        params.get("sap_id", "?"),
        sorted(current_sem_labels),
    )

    # ── 2. Semester via direct ComboBox_Select AJAX ───────────────────────────
    # Semester listbox items are injected into the DOM via AJAX after year selection.
    # Clicking them does not fire ComboBox_Select to the SAP server for dynamically-
    # injected items — we POST the event directly and eval() the JS delta response.
    sem_opts = await frame.evaluate("""
        () => {
            let items = Array.from(document.querySelectorAll('#WD35 .lsListbox__value'));
            if (items.length > 0)
                return items.map(el => ({
                    id:  el.id,
                    label: el.innerText.trim(),
                    key: el.getAttribute('data-itemkey') || ''
                }));
            return Array.from(document.querySelectorAll('.lsListbox__value'))
                        .filter(el => /semester/i.test(el.innerText))
                        .map(el => ({
                            id:  el.id,
                            label: el.innerText.trim(),
                            key: el.getAttribute('data-itemkey') || ''
                        }));
        }
    """)
    if not sem_opts:
        raise RuntimeError("Semester options not found after year selection.")

    sem_target = params.get("semester_label") or "Semester VI"
    target_sem = next((s for s in sem_opts if s["label"] == sem_target), None)
    if not target_sem:
        logger.warning(
            "[%s] Semester %r not found in %s; using last",
            params.get("sap_id", "?"),
            sem_target,
            [s["label"] for s in sem_opts],
        )
        target_sem = sem_opts[-1]

    logger.info(
        "[%s] Target semester: label=%r key=%r id=%r",
        params.get("sap_id", "?"),
        target_sem["label"],
        target_sem["key"],
        target_sem["id"],
    )

    # Semester combobox = 2nd ct=CB input (year is 1st)
    sem_cb_id = await frame.evaluate("""
        () => {
            const cbs = Array.from(document.querySelectorAll("input[ct='CB']"))
                             .filter(el => el.id && el.id.startsWith('WD'));
            return cbs.length >= 2 ? cbs[1].id : (cbs.length ? cbs[0].id : 'WD33');
        }
    """)
    logger.info("[%s] Semester combobox id: %s", params.get("sap_id", "?"), sem_cb_id)

    # Capture form params needed for AJAX POST
    form_params = await frame.evaluate("""
        () => ({
            secureId: (document.querySelector('input[name="sap-wd-secure-id"]') || {}).value || '',
            appName:  (document.querySelector('input[name="fesrAppName"]') || {}).value || 'ZSVKM_STUDENT_ATTENDANCE2',
            frameUrl: window.location.href
        })
    """)

    sem_key = target_sem.get("key", "")
    if sem_key and form_params.get("secureId") and form_params.get("frameUrl"):
        ajax_result = await frame.evaluate(
            """
            async ({semCbId, semKey, secureId, appName, frameUrl}) => {
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
                try {
                    const resp = await fetch(frameUrl, {
                        method:      'POST',
                        headers:     {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
                        body:        body,
                        credentials: 'include',
                    });
                    const ct   = resp.headers.get('content-type') || '';
                    const text = await resp.text();
                    if (ct.includes('javascript') || ct.includes('text/html') || text.includes('<updates>')) {
                        try { eval(text); } catch (_) {}
                    }
                    return { ok: resp.ok, status: resp.status, len: text.length, preview: text.slice(0, 200) };
                } catch (e) {
                    return { ok: false, error: String(e) };
                }
            }
            """,
            {
                "semCbId": sem_cb_id,
                "semKey": sem_key,
                "secureId": form_params["secureId"],
                "appName": form_params.get("appName", "ZSVKM_STUDENT_ATTENDANCE2"),
                "frameUrl": form_params["frameUrl"],
            },
        )
        logger.info(
            "[%s] Semester AJAX: ok=%s status=%s len=%s",
            params.get("sap_id", "?"),
            ajax_result.get("ok"),
            ajax_result.get("status"),
            ajax_result.get("len"),
        )
    else:
        # No data-itemkey: fall back to click
        logger.warning(
            "[%s] No semKey/secureId for semester — falling back to click id=%s",
            params.get("sap_id", "?"),
            target_sem.get("id"),
        )
        if target_sem.get("id"):
            await _wd_click(frame, target_sem["id"])

    # Wait for SAP WD delta to settle (may shift report-type IDs)
    await asyncio.sleep(2.0)

    # ── 3. Report Type — Detail Report ───────────────────────────────────────
    # Find report-type combobox: the LAST ct=CB input in the form
    # (year=1st, semester=2nd, report-type=last).
    # NOTE: Do NOT send ComboBox_Select AJAX for this widget — SAP does not
    # expect it for the report-type selector and it causes form reset in some layouts.
    # A plain mouse-click + 2s wait + 15s date-field poll is sufficient.
    report_trigger_id = await frame.evaluate("""
        () => {
            const boxes = Array.from(document.querySelectorAll("input[ct='CB']"))
                               .filter(el => el.id && el.id.startsWith('WD'));
            return boxes.length > 0 ? boxes[boxes.length - 1].id : null;
        }
    """)
    logger.info(
        "[%s] Report-type combobox trigger: %s",
        params.get("sap_id", "?"),
        report_trigger_id,
    )

    if not report_trigger_id:
        raise RuntimeError("Report-type combobox not found.")

    await _wd_click(frame, report_trigger_id)
    await asyncio.sleep(0.8)

    detail_info = await frame.evaluate("""
        () => {
            for (const el of document.querySelectorAll('.lsListbox__value')) {
                if (/detail/i.test(el.innerText))
                    return { id: el.id, key: el.getAttribute('data-itemkey') || '', text: el.innerText.trim() };
            }
            return null;
        }
    """)
    logger.info(
        "[%s] Detail report option found: %s", params.get("sap_id", "?"), detail_info
    )

    if not detail_info or not detail_info.get("id"):
        raise RuntimeError("Detail report option not found in report-type dropdown.")

    await _wd_click(frame, detail_info["id"])
    logger.info(
        "[%s] Detail report clicked (id=%s text=%r)",
        params.get("sap_id", "?"),
        detail_info["id"],
        detail_info.get("text"),
    )

    # Wait 2s for AJAX to settle, then poll up to 15s for date inputs to appear
    await asyncio.sleep(2.0)

    # ── 4. Date fields — poll up to 15 seconds ────────────────────────────────
    date_input_ids: list = []
    for _poll in range(30):
        date_input_ids = await frame.evaluate("""
            () => {
                let ids = Array.from(document.querySelectorAll("input[ct='I']"))
                               .filter(el => el.id && el.id.startsWith('WD') && el.type !== 'hidden')
                               .map(el => el.id);
                if (ids.length >= 2) return ids;
                // Fallback: any visible text WD input
                ids = Array.from(document.querySelectorAll("input[type='text']"))
                           .filter(el => el.id && el.id.startsWith('WD') && el.offsetParent !== null)
                           .map(el => el.id);
                return ids;
            }
        """)
        if len(date_input_ids) >= 2:
            logger.info(
                "[%s] Date inputs found on poll %d: %s",
                params.get("sap_id", "?"),
                _poll + 1,
                date_input_ids[:2],
            )
            break
        await asyncio.sleep(0.5)

    # Diagnostic: log all WD inputs currently in the form
    input_diag = await frame.evaluate("""
        () => Array.from(document.querySelectorAll('input'))
            .filter(el => el.id && el.id.startsWith('WD') && el.type !== 'hidden')
            .map(el => ({id: el.id, ct: el.getAttribute('ct'), visible: el.offsetParent !== null}))
    """)
    logger.info(
        "[%s] WD inputs after Detail selection: %s",
        params.get("sap_id", "?"),
        input_diag,
    )

    has_dates = len(date_input_ids) >= 2
    if not has_dates:
        logger.warning(
            "[%s] Date fields did not appear after 15s — Path B: submit without dates",
            params.get("sap_id", "?"),
        )
    else:
        start_v = params.get("start_date") or "01.06.2025"
        end_v = params.get("end_date") or datetime.now(_IST).strftime("%d.%m.%Y")
        await frame.fill(f"#{date_input_ids[0]}", start_v)
        await frame.fill(f"#{date_input_ids[1]}", end_v)
        for iid in date_input_ids[:2]:
            await frame.evaluate(
                """(id) => {
                    var el = document.getElementById(id);
                    if (el) {
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                        el.dispatchEvent(new Event('blur', {bubbles: true}));
                    }
                }""",
                iid,
            )
        logger.info(
            "[%s] Dates filled: %s → %s (fields: %s, %s)",
            params.get("sap_id", "?"),
            start_v,
            end_v,
            date_input_ids[0],
            date_input_ids[1],
        )
        await asyncio.sleep(0.5)

    # ── 5. Submit ─────────────────────────────────────────────────────────────
    submit_id = await frame.evaluate("""
        () => {
            if (document.getElementById('WD52')) return 'WD52';
            // WD51 for layouts with fewer year options (2nd year)
            if (document.getElementById('WD51')) return 'WD51';
            // Generic: last ct=B div/button with WD id
            const btns = Array.from(document.querySelectorAll("[ct='B']"))
                .filter(el => el.id && el.id.startsWith('WD'));
            if (btns.length > 0) return btns[btns.length - 1].id;
            if (document.getElementById('WD46')) return 'WD46';
            return null;
        }
    """)
    logger.info("[%s] Submit button id=%s", params.get("sap_id", "?"), submit_id)
    if not submit_id:
        raise RuntimeError("Submit button not found (WD46/WD51/WD52).")

    # Path A: try to capture PDF directly from submit network response
    pdf_from_response = None
    try:
        async with page.expect_response(
            lambda r: (
                "sap-wd-filedownload=X" in r.url
                or "sap-wd-resource-id=" in r.url
                or r.url.lower().endswith(".pdf")
            ),
            timeout=12000,
        ) as resp_info:
            await _wd_click(frame, submit_id)
        direct_resp = await resp_info.value
        if direct_resp.ok:
            body = await direct_resp.body()
            if body[:4] == b"%PDF":
                pdf_from_response = body
                logger.info(
                    "[%s] Path A: captured PDF directly from submit response (%d bytes)",
                    params.get("sap_id", "?"),
                    len(body),
                )
    except PlaywrightTimeout:
        # No direct-download response — submit click already fired in expect_response context;
        # no need to click again
        logger.info(
            "[%s] No direct PDF response from submit — proceeding to DOM poll",
            params.get("sap_id", "?"),
        )

    if pdf_from_response is not None:
        return _enrich_with_course_hours(
            _merge_theory_practical_rows(_parse_pdf_attendance(pdf_from_response))
        )

    # ── 6. Path B/C: Poll DOM for PDF object URL (up to 50s) ─────────────────
    obj_url = None
    for _i in range(100):
        obj_url = await frame.evaluate("""
            () => {
                const el = document.querySelector(
                    'object[ct="PDF"], object[type="application/pdf"], embed[type="application/pdf"]'
                );
                return el ? (el.data || el.src || null) : null;
            }
        """)
        if obj_url:
            logger.info(
                "[%s] Path B: PDF object found in DOM (poll %d): %s",
                params.get("sap_id", "?"),
                _i + 1,
                obj_url[:100],
            )
            break
        await asyncio.sleep(0.5)

    if not obj_url:
        # Path C: inspect frame source HTML for PDF URL
        try:
            frame_resp = await page.context.request.get(frame.url, timeout=15000)
            if frame_resp.ok:
                html_body = await frame_resp.text()
                m = re.search(
                    r'(?:data|src)=["\']([^"\']+\.pdf[^"\']*)["\']', html_body, re.I
                )
                if m:
                    obj_url = m.group(1)
                    logger.info(
                        "[%s] Path C: PDF URL found in frame HTML: %s",
                        params.get("sap_id", "?"),
                        obj_url[:100],
                    )
        except Exception as exc:
            logger.warning(
                "[%s] Path C frame HTML fetch failed: %s",
                params.get("sap_id", "?"),
                exc,
            )

    if not obj_url:
        err_msg = await frame.evaluate("""
            () => {
                const el = document.querySelector('.lsMessage__text, [role="alert"]');
                return el ? el.innerText.trim() : null;
            }
        """)
        # Log diagnostic inputs to help debug future layout variants
        diag_inputs = await frame.evaluate("""
            () => Array.from(document.querySelectorAll('input'))
                .filter(el => el.id && el.id.startsWith('WD') && el.type !== 'hidden')
                .map(el => el.id)
        """)
        logger.error(
            "[%s] PDF not found. SAP message: %r. WD inputs: %s",
            params.get("sap_id", "?"),
            err_msg,
            diag_inputs,
        )
        raise RuntimeError(f"PDF failed: {err_msg or 'Report generation timeout.'}")

    if not obj_url.startswith("http"):
        obj_url = urljoin(frame.url, obj_url)

    # ── 7. Fetch PDF bytes (context.request then frame-context fetch) ─────────
    pdf_bytes = None
    last_status: Any = None
    for attempt in range(8):
        try:
            resp = await page.context.request.get(
                obj_url,
                timeout=15000,
                headers={"Referer": frame.url, "Accept": "application/pdf,*/*;q=0.9"},
            )
            last_status = resp.status
            if resp.ok:
                body = await resp.body()
                if body[:4] == b"%PDF":
                    pdf_bytes = body
                    logger.info(
                        "[%s] PDF fetched via context.request (%d bytes) attempt %d",
                        params.get("sap_id", "?"),
                        len(body),
                        attempt + 1,
                    )
                    break
        except PlaywrightTimeout:
            last_status = "timeout"
            logger.warning(
                "[%s] PDF request timeout attempt %d",
                params.get("sap_id", "?"),
                attempt + 1,
            )
        except Exception as exc:
            last_status = f"error:{type(exc).__name__}"
            logger.warning(
                "[%s] PDF request failed attempt %d: %s",
                params.get("sap_id", "?"),
                attempt + 1,
                exc,
            )

        await asyncio.sleep(1.0)
        # Check if object URL updated after server-side render
        refreshed = await frame.evaluate("""
            () => {
                const el = document.querySelector(
                    'object[ct="PDF"], object[type="application/pdf"], embed[type="application/pdf"]'
                );
                return el ? (el.data || el.src || null) : null;
            }
        """)
        if refreshed:
            new_url = (
                refreshed
                if refreshed.startswith("http")
                else urljoin(frame.url, refreshed)
            )
            if new_url != obj_url:
                logger.info("[%s] PDF object URL refreshed", params.get("sap_id", "?"))
                obj_url = new_url

    if not pdf_bytes:
        # Final fallback: fetch from inside frame JS context (keeps exact SAP session cookies)
        fetch_result = await frame.evaluate(
            """
            async (url) => {
                const controller = new AbortController();
                const tid = setTimeout(() => controller.abort(), 15000);
                try {
                    const resp = await fetch(url, { credentials: 'include', signal: controller.signal });
                    const ab = await resp.arrayBuffer();
                    const bytes = new Uint8Array(ab);
                    let bin = '';
                    const chunk = 0x8000;
                    for (let i = 0; i < bytes.length; i += chunk)
                        bin += String.fromCharCode(...bytes.subarray(i, i + chunk));
                    clearTimeout(tid);
                    return { ok: resp.ok, status: resp.status,
                             ct: resp.headers.get('content-type') || '', b64: btoa(bin) };
                } catch (e) {
                    clearTimeout(tid);
                    return { ok: false, status: 0, ct: '', error: String(e) };
                }
            }
            """,
            obj_url,
        )
        if fetch_result and fetch_result.get("ok") and fetch_result.get("b64"):
            candidate = base64.b64decode(fetch_result["b64"])
            if candidate[:4] == b"%PDF":
                pdf_bytes = candidate
                logger.info(
                    "[%s] PDF fetched via frame JS fetch (%d bytes)",
                    params.get("sap_id", "?"),
                    len(candidate),
                )
            else:
                logger.warning(
                    "[%s] Frame JS fetch: not a PDF (ct=%s)",
                    params.get("sap_id", "?"),
                    fetch_result.get("ct"),
                )
        else:
            logger.warning(
                "[%s] Frame JS fetch failed: status=%s error=%s",
                params.get("sap_id", "?"),
                (fetch_result or {}).get("status"),
                (fetch_result or {}).get("error"),
            )

    if not pdf_bytes:
        raise RuntimeError(
            f"PDF download failed (last_status={last_status or 'unknown'})"
        )

    merged = _merge_theory_practical_rows(_parse_pdf_attendance(pdf_bytes))
    return _enrich_with_course_hours(merged)


def _parse_pdf_attendance(pdf_bytes: bytes) -> list[dict]:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return []

    try:
        lines = []
        for pg in doc:
            lines.extend(pg.get_text().split("\n"))

        sr_re = re.compile(r"^\d+$")
        records = []
        i = 0
        while i < len(lines) - 5:
            s0 = lines[i].strip()
            if not sr_re.match(s0):
                i += 1
                continue

            found_match = False
            for offset in range(2, 10):
                if i + offset >= len(lines):
                    break
                val = lines[i + offset].strip()
                if val in _VALID_STATUSES:
                    course_name = lines[i + 1].strip()
                    records.append((course_name, val))
                    i += offset + 1
                    found_match = True
                    break

            if not found_match:
                i += 1

        counts = defaultdict(lambda: {"attended": 0, "total": 0, "not_updated": 0})
        for course, status in records:
            if status == "NU":
                counts[course]["not_updated"] += 1
            else:
                counts[course]["total"] += 1
                if status in _PRESENT_STATUSES:
                    counts[course]["attended"] += 1

        results = []
        for sub, c in counts.items():
            results.append(
                {
                    "subject": sub,
                    "attended": c["attended"],
                    "total": c["total"],
                    "not_updated": c["not_updated"],
                    "last_entry": "",
                    "percentage": round(c["attended"] / c["total"] * 100, 1)
                    if c["total"] > 0
                    else (None if c["not_updated"] > 0 else 0),
                }
            )
        return sorted(results, key=lambda x: x["subject"])
    finally:
        doc.close()


def _subject_component(subject: str) -> Optional[str]:
    m = _SECTION_RE.search(subject)
    if not m:
        return None
    return "practical" if m.group(1).upper() == "P" else "theory"


def _normalize_course_name(name: str) -> str:
    name = _ELECTIVE_PFX_RE.sub("", name)
    part_split = re.split(r"[TP]\d+", name, flags=re.IGNORECASE)
    if part_split:
        name = part_split[0]
    lowered = name.lower()
    for hint in _CUT_HINTS:
        idx = lowered.find(hint)
        if idx > 0:
            name = name[:idx]
            lowered = name.lower()
            break
    name = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    name = re.sub(r"\s+", " ", name).strip()
    tokens = [
        t
        for t in name.split()
        if t not in _NOISE_TOKENS and not re.fullmatch(r"[a-z]\d+", t)
    ]
    return " ".join(tokens)


def _course_identity_key(name: str) -> str:
    norm = _normalize_course_name(name)
    if not norm:
        return ""
    tokens = norm.split()
    compact = [t[:5] for t in tokens[:3]]
    return " ".join(compact)


def _display_subject_name(name: str) -> str:
    base = re.split(r"[TP]\d+", name, flags=re.IGNORECASE)[0]
    base = _ELECTIVE_PFX_RE.sub("", base)
    base = re.sub(r"\s+", " ", base).strip(" -")
    return base or name


def _merge_theory_practical_rows(subjects: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}

    def pick_merge_key(candidate: str) -> str:
        if candidate in merged:
            return candidate
        c_tokens = set(candidate.split())
        best_key = candidate
        best_score = 0.0
        for existing in merged.keys():
            if candidate in existing or existing in candidate:
                score = min(len(candidate), len(existing)) / max(
                    len(candidate), len(existing)
                )
            else:
                e_tokens = set(existing.split())
                token_score = len(c_tokens & e_tokens) / max(
                    1, len(c_tokens | e_tokens)
                )
                seq_score = difflib.SequenceMatcher(None, candidate, existing).ratio()
                score = max(token_score, seq_score)
            if score > best_score:
                best_score = score
                best_key = existing
        return best_key if best_score >= 0.72 else candidate

    for s in subjects:
        raw_subject = s.get("subject", "")
        key = _course_identity_key(raw_subject)
        if not key:
            key = raw_subject.lower().strip()
        key = pick_merge_key(key)
        if key not in merged:
            merged[key] = {
                "subject": _display_subject_name(raw_subject),
                "attended": 0,
                "total": 0,
                "not_updated": 0,
                "last_entry": "",
            }
        merged[key]["attended"] += int(s.get("attended") or 0)
        merged[key]["total"] += int(s.get("total") or 0)
        merged[key]["not_updated"] += int(s.get("not_updated") or 0)
        if s.get("last_entry"):
            merged[key]["last_entry"] = s["last_entry"]

    out = []
    for item in merged.values():
        if item["total"] > 0:
            pct = round(item["attended"] / item["total"] * 100, 1)
        elif item["not_updated"] > 0:
            pct = None
        else:
            pct = 0
        item["percentage"] = pct
        out.append(item)
    return sorted(out, key=lambda x: x["subject"])


def _load_course_durations() -> dict[str, dict]:
    if not COURSE_DURATIONS_PATH.exists():
        return {}

    with open(COURSE_DURATIONS_PATH, encoding="utf-8") as f:
        rows = json.load(f)

    duration_map: dict[str, dict] = {}
    for row in rows:
        key = _course_identity_key(row.get("course", ""))
        if not key:
            continue
        duration_map[key] = {
            "total_hours": int(row.get("total_hours") or 0),
            "lecture_hrs": int(row.get("lecture_hrs") or 0),
            "practical_hrs": int(row.get("practical_hrs") or 0),
            "tutorial_hrs": int(row.get("tutorial_hrs") or 0),
        }

    # Overlay user-submitted hours from Supabase.
    # Run in a thread pool so we don't block the async event loop.
    def _fetch_supabase_overrides() -> list:
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/course_hours?select=course,total_hours",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())

    try:
        if SUPABASE_URL and SUPABASE_KEY:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                custom_rows = pool.submit(_fetch_supabase_overrides).result(timeout=6)
            for row in custom_rows:
                key = _course_identity_key(row.get("course", ""))
                if not key:
                    continue
                existing = duration_map.get(
                    key, {"lecture_hrs": 0, "practical_hrs": 0, "tutorial_hrs": 0}
                )
                existing["total_hours"] = int(row.get("total_hours") or 0)
                duration_map[key] = existing
    except Exception:
        pass

    return duration_map


def _best_duration_match(subject: str, duration_map: dict[str, dict]) -> Optional[dict]:
    key = _course_identity_key(subject)
    if not key:
        return None
    if key in duration_map:
        return duration_map[key]

    for k, v in duration_map.items():
        if key in k or k in key:
            ratio = min(len(key), len(k)) / max(len(key), len(k))
            if ratio >= 0.6:
                return v

    tokens = set(key.split())
    best = None
    best_score = 0.0
    for k, v in duration_map.items():
        kt = set(k.split())
        if not kt:
            continue
        score = len(tokens & kt) / max(len(tokens), len(kt))
        if score > best_score and score >= 0.6:
            best_score = score
            best = v
    return best


def _request_cache_key(req: AttendanceRequest) -> str:
    payload = {
        "sap_id": req.sap_id,
        "year_key": req.year_key or "",
        "semester_label": req.semester_label or "",
        "start_date": req.start_date or "",
        "end_date": req.end_date or "",
    }
    digest = hashlib.sha1(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"data:{req.sap_id}:{digest}"


def _enrich_with_course_hours(subjects: list[dict]) -> list[dict]:
    duration_map = _load_course_durations()
    for s in subjects:
        s["pending"] = None
        s["to_attend"] = None

        meta = _best_duration_match(s.get("subject", ""), duration_map)
        if not meta:
            continue

        total_hours = int(meta.get("total_hours") or 0)
        if total_hours <= 0:
            continue

        attended = int(s.get("attended") or 0)
        conducted = int(s.get("total") or 0)
        s["pending"] = max(0, total_hours - conducted)
        s["to_attend"] = max(0, math.ceil(0.8 * total_hours) - attended)

    return subjects


# ---------------------------------------------------------------------------
# 5. Worker & Lifespan
# ---------------------------------------------------------------------------


async def _worker():
    while True:
        sap_id, password, params, job_type, cache_key = await _queue.get()
        _tracker.mark_processing(sap_id)
        try:
            async with _scrape_semaphore:
                result = await asyncio.wait_for(
                    _scrape_logic(sap_id, password, params, job_type),
                    timeout=SCRAPE_TIMEOUT_SECONDS,
                )
            _cache.set(cache_key, result)
            _cache.set(f"data_latest:{sap_id}", cache_key)
        except asyncio.TimeoutError:
            logger.error(
                "[%s] Worker task timed out after %ss", sap_id, SCRAPE_TIMEOUT_SECONDS
            )
            _cache.set(
                cache_key,
                {"error": "Attendance fetch timed out. Please retry."},
            )
            _cache.set(f"data_latest:{sap_id}", cache_key)
        except Exception as e:
            logger.exception("[%s] Worker task failed", sap_id)
            _cache.set(cache_key, {"error": str(e)})
            _cache.set(f"data_latest:{sap_id}", cache_key)
        finally:
            _tracker.mark_done(sap_id)
            _queue.task_done()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with async_playwright() as pw:
        _state.pw_instance = pw
        worker_task = asyncio.create_task(_worker())
        yield
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        if _state.browser:
            try:
                await _state.browser.close()
            except Exception:
                logger.debug("Browser already closed during shutdown")


# ---------------------------------------------------------------------------
# 6. Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/options")
async def get_options(req: AttendanceOptionsRequest):
    cached = _cache.get(f"options:{req.sap_id}")
    if cached is not None:
        return {"options": cached}

    async with _scrape_semaphore:
        try:
            result = await _scrape_logic(req.sap_id, req.sap_password, {}, "options")
            if isinstance(result, dict) and "error" in result:
                return {"options": None, "error": result["error"]}
            _cache.set(f"options:{req.sap_id}", result)
            return {"options": result}
        except Exception as e:
            return {"options": None, "error": str(e)}


@router.post("", response_model=AttendanceResponse)
async def request_attendance(req: AttendanceRequest):
    key = _request_cache_key(req)
    cached = _cache.get(key)
    if cached is not None:
        if isinstance(cached, dict) and "error" in cached:
            # Do not pin users to stale/temporary failures (e.g., SAP timeout).
            # Clear the error cache and allow a fresh retry request.
            _cache.delete(key)
        else:
            return AttendanceResponse(status="ok", data=cached)

    if _tracker.is_processing(req.sap_id):
        return AttendanceResponse(status="processing")
    if _tracker.is_queued(req.sap_id):
        return AttendanceResponse(status="queued", queue_position=_tracker.depth)
    if _queue.full():
        return AttendanceResponse(
            status="error",
            data={"error": "Attendance queue is full. Please try again in a minute."},
        )

    _tracker.mark_queued(req.sap_id)
    _cache.set(f"data_latest:{req.sap_id}", key)
    await _queue.put((req.sap_id, req.password, req.model_dump(), "data", key))
    return AttendanceResponse(status="queued", queue_position=_tracker.depth)


@router.get("/status/{sap_id}")
async def poll_status(sap_id: str):
    active_key = _cache.get(f"data_latest:{sap_id}")
    res = _cache.get(active_key) if active_key else None
    if res is not None:
        if isinstance(res, dict) and "error" in res:
            if active_key:
                _cache.delete(active_key)
            return {"status": "error", "error": res["error"]}
        return {"status": "ok", "subjects": res}
    if _tracker.is_processing(sap_id):
        return {"status": "processing"}
    if _tracker.is_queued(sap_id):
        return {"status": "queued", "queue_position": _tracker.depth}
    # If data_latest pointer exists but result was just cleared (race between error
    # cache deletion and new job enqueue), treat it as processing rather than expired.
    if active_key:
        return {"status": "processing"}
    return {
        "status": "error",
        "error": "No active job found. Please submit a new request.",
    }
