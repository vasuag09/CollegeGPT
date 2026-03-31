"""
NM-GPT – SAP NetWeaver Attendance Scraper (httpx edition)

Logs into the SAP NetWeaver portal with student-provided credentials,
navigates to the attendance page, fills the Detail Report form, intercepts
the generated PDF, and returns subject-wise attendance computed from it.

Uses httpx (plain HTTP) instead of Playwright/Chromium. Memory footprint per
request: ~5 MB vs ~250 MB with a headless browser — safe for 50+ concurrent
users on Render's free tier.

CAPTCHA: The login page has a client-side JS canvas CAPTCHA. The code is stored
in window.code (set by a Captcha() JS function). We execute that JS in a
lightweight V8 sandbox (py_mini_racer) with DOM stubs — no OCR, no browser.

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
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse

import fitz  # PyMuPDF
import httpx
from bs4 import BeautifulSoup

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

# SAP WebDynpro SAPEVENTQUEUE suffix — tells SAP to return a delta response
_WD_DELTA_SUFFIX = "~E002ResponseData~E004delta~E005ClientAction~E004submit~E003~E002~E003"

_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _check_portal_window() -> None:
    """Raise RuntimeError if outside the SAP portal access window (6 PM – 7 AM IST)."""
    now_ist = datetime.now(_IST)
    hour = now_ist.hour
    if _PORTAL_CLOSE_HOUR <= hour < _PORTAL_OPEN_HOUR:
        open_time = now_ist.replace(hour=_PORTAL_OPEN_HOUR, minute=0, second=0, microsecond=0)
        raise RuntimeError(
            f"The SAP portal is only accessible between 6:00 PM and 7:00 AM IST. "
            f"Current IST time: {now_ist.strftime('%I:%M %p')}. "
            f"Please try again after {open_time.strftime('%I:%M %p')} IST."
        )


# ---------------------------------------------------------------------------
# SAP HTTP session
# ---------------------------------------------------------------------------

class _SapSession:
    """
    Thin wrapper around httpx.Client that maintains SAP portal session state:
    cookies, the WebDynpro frame URL, sap-wd-secure-id, and fesrAppName.
    """

    def __init__(self):
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=30.0,
            verify=False,   # SAP NetWeaver on port 50001 uses self-signed certs
            headers={
                "User-Agent": _CHROME_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
        )
        self._frame_url: str = ""
        self._secure_id: str = ""
        self._app_name: str = "ZSVKM_STUDENT_ATTENDANCE2"
        self._wd_html: str = ""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._client.close()

    # ── Login ────────────────────────────────────────────────────────────────

    def login(self, sap_id: str, sap_password: str) -> None:
        logger.info("Navigating to SAP portal...")
        resp = self._client.get(SAP_PORTAL_URL)
        html = resp.text

        # Extract form action
        soup = BeautifulSoup(html, "lxml")
        form = soup.find("form", id="logonForm") or soup.find("form")
        if form and form.get("action"):
            action = form["action"]
            if not action.startswith("http"):
                action = urljoin(str(resp.url), action)
        else:
            action = str(resp.url)

        # Collect hidden fields (CSRF tokens, etc.)
        hidden: dict[str, str] = {}
        if form:
            for inp in form.find_all("input", type="hidden"):
                if inp.get("name"):
                    hidden[inp["name"]] = inp.get("value", "")

        # Solve the client-side JS CAPTCHA
        captcha_code = self._extract_captcha(html)
        logger.info("CAPTCHA resolved (client-side JS)")

        # POST login
        data = {
            **hidden,
            "logonuidfield": sap_id,
            "logonpassfield": sap_password,
            "txtInput": str(captcha_code),
        }
        # Also check for the submit button name field (SAP sometimes uses it)
        if form:
            btn = form.find("input", type="submit") or form.find("button", type="submit")
            if btn and btn.get("name"):
                data[btn["name"]] = btn.get("value", "")
        # Fallback: SAP default button ID
        if "Button1" not in data and not any("btn" in k.lower() for k in data):
            data["Button1"] = "Log On"

        resp = self._client.post(
            action,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        logger.info(
            "Login POST response: url=%s status=%d html_snippet=%r",
            str(resp.url)[:80], resp.status_code, resp.text[:300],
        )

        # Use a DOM check (not a string search) — the portal home page may contain
        # "logonuidfield" in its JavaScript source even after successful login.
        # We check for the actual <input id="logonuidfield"> element, same as
        # the old Playwright version did with page.query_selector("#logonuidfield").
        login_soup = BeautifulSoup(resp.text, "lxml")
        title_el = login_soup.find("title")
        page_title = title_el.get_text(strip=True) if title_el else ""
        # The portal home page title is "SAP NetWeaver Portal".
        # The login page title does NOT contain "NetWeaver Portal".
        # The portal home page also contains <input id="logonuidfield"> (embedded
        # logout widget), so checking for that element is a false positive.
        logged_in = "NetWeaver Portal" in page_title or "SAP Portal" in page_title
        logger.info("Login result: title=%r logged_in=%s", page_title[:80], logged_in)
        if not logged_in:
            raise RuntimeError(
                "SAP login failed — credentials or captcha rejected. "
                "Check your SAP credentials. Do NOT retry automatically to avoid account lockout."
            )

        self._home_html = resp.text
        self._home_url = str(resp.url)
        logger.info("SAP login successful for %s***", sap_id[:4])

    def _extract_captcha(self, html: str) -> str:
        """
        Extract the CAPTCHA code from the login page JS without a browser.

        Strategy:
        1. Try py_mini_racer (V8) with DOM stubs to execute the Captcha() function
        2. Fall back to regex if window.code is a string literal in the source
        3. Return empty string (SAP may still accept if captcha is optional)
        """
        soup = BeautifulSoup(html, "lxml")
        captcha_scripts = [
            s.string for s in soup.find_all("script")
            if s.string and "Captcha" in s.string
        ]

        logger.info(
            "CAPTCHA scripts found: %d; first 400 chars: %r",
            len(captcha_scripts),
            captcha_scripts[0][:400] if captcha_scripts else "(none)",
        )

        if captcha_scripts:
            code = self._run_captcha_js(captcha_scripts[0])
            if code:
                return code

        # Regex fallback: var code = "XYZ" or window.code = "XYZ"
        m = re.search(
            r'(?:window\.code|var\s+code)\s*=\s*["\']([A-Za-z0-9]{3,10})["\']',
            html,
        )
        if m:
            logger.info("CAPTCHA extracted via regex")
            return m.group(1)

        logger.warning("Could not extract CAPTCHA — submitting empty string")
        return ""

    @staticmethod
    def _run_captcha_js(script_src: str) -> str:
        """Execute captcha JS in a V8 sandbox (py_mini_racer) with DOM stubs."""
        try:
            import py_mini_racer  # type: ignore
        except ImportError:
            logger.warning("py_mini_racer not installed — CAPTCHA JS execution skipped")
            return ""

        # Full DOM stubs — every API the SVKM captcha JS may call.
        # Do NOT wrap the script in JS try{}catch{}: function declarations
        # inside blocks are block-scoped in V8, so Captcha() would be invisible
        # outside the try block. Instead, stub all APIs so nothing throws.
        dom_stubs = """
var Event = function(type, init) { this.type = type || ''; };
Event.prototype = { preventDefault: function(){}, stopPropagation: function(){},
                    stopImmediatePropagation: function(){} };
var CustomEvent = Event;
var MouseEvent = Event;
var KeyboardEvent = Event;
var UIEvent = Event;
var navigator = {
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    language: 'en-US', platform: 'Win32', appName: 'Netscape',
    appVersion: '5.0', cookieEnabled: true, onLine: true
};
var screen = { width: 1920, height: 1080, colorDepth: 24 };
var location = { href: '', hostname: '', protocol: 'https:', search: '', hash: '' };
var _ctx = {
    fillText: function(){}, strokeText: function(){},
    measureText: function(){ return {width:50}; },
    fillRect: function(){}, clearRect: function(){}, strokeRect: function(){},
    beginPath: function(){}, closePath: function(){},
    arc: function(){}, arcTo: function(){},
    fill: function(){}, stroke: function(){},
    moveTo: function(){}, lineTo: function(){},
    quadraticCurveTo: function(){}, bezierCurveTo: function(){},
    rotate: function(){}, translate: function(){}, scale: function(){},
    save: function(){}, restore: function(){},
    createLinearGradient: function(){ return {addColorStop:function(){}}; },
    font: '', fillStyle: '', strokeStyle: '', lineWidth: 1,
    globalAlpha: 1, textAlign: 'left', textBaseline: 'alphabetic',
    canvas: { width: 200, height: 60 }
};
var _elem = {
    getContext: function(){ return _ctx; },
    width: 200, height: 60, style: {}, id: '',
    innerHTML: '', innerText: '', value: '',
    addEventListener: function(){}, removeEventListener: function(){},
    dispatchEvent: function(){},
    appendChild: function(){}, removeChild: function(){},
    setAttribute: function(){}, getAttribute: function(){ return ''; }
};
var document = {
    getElementById: function(id){ return _elem; },
    createElement: function(tag){ return _elem; },
    createElementNS: function(ns, tag){ return _elem; },
    cookie: '',
    addEventListener: function(){}, removeEventListener: function(){},
    captureEvents: function(){}, releaseEvents: function(){}
};
var window = this;
var code = '';
"""
        ctx = py_mini_racer.MiniRacer()
        try:
            ctx.eval(dom_stubs + script_src)
        except Exception as exc:
            logger.warning("py_mini_racer: error loading captcha JS: %s", exc)
            return ""
        # Trigger via window.onload (same as the browser) then also call directly
        try:
            ctx.eval("if (typeof window.onload === 'function') window.onload();")
        except Exception as exc:
            logger.warning("py_mini_racer: window.onload threw: %s", exc)
        try:
            ctx.eval("if (typeof Captcha === 'function') Captcha();")
        except Exception as exc:
            logger.warning("py_mini_racer: Captcha() threw: %s", exc)
        try:
            result = ctx.eval(
                "(typeof window.code !== 'undefined' && window.code) ? window.code : "
                "(typeof code !== 'undefined' ? code : '')"
            )
            logger.info("py_mini_racer result: %r", str(result)[:20])
            if result and str(result).strip():
                logger.info("CAPTCHA solved via py_mini_racer")
                return str(result)
        except Exception as exc:
            logger.warning("py_mini_racer: error reading window.code: %s", exc)
        return ""

    # ── Navigate to attendance WebDynpro frame ───────────────────────────────

    def navigate_to_attendance(self) -> None:
        """
        Navigate directly to the attendance WebDynpro app via dispatcher URL.
        The SAP portal renders its navigation menu via JavaScript, so scraping
        the home HTML for links does not work — we go straight to the app.
        Sets self._frame_url, self._wd_html, self._secure_id, self._app_name.
        """
        # Derive base origin from portal URL (e.g. https://sdc-sppap1.svkm.ac.in:50001)
        from urllib.parse import urlparse
        parsed = urlparse(self._home_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        # SAP WebDynpro dispatcher URL — same pattern as every other app on this portal
        # e.g. /webdynpro/dispatcher/sap.com/tc~sec~ume~wd~enduser/LogonHelpApp
        wd_url = f"{base}/webdynpro/dispatcher/sap.com/ZSVKM_STUDENT_ATTENDANCE2"
        logger.info("Navigating directly to attendance WebDynpro: %s", wd_url)

        resp = self._client.get(wd_url)
        logger.info(
            "WebDynpro direct GET: url=%s status=%s snippet=%r",
            str(resp.url)[:120],
            resp.status_code,
            resp.text[:300],
        )

        if "ZSVKM_STUDENT_ATTENDANCE2" in str(resp.url):
            self._frame_url = str(resp.url)
            self._wd_html = resp.text
        else:
            # The dispatcher may redirect to a portal page containing an iframe
            soup2 = BeautifulSoup(resp.text, "lxml")
            iframe = soup2.find("iframe", src=re.compile(r"ZSVKM_STUDENT_ATTENDANCE2", re.I))
            if not iframe:
                for fr in soup2.find_all(["iframe", "frame"]):
                    src = fr.get("src", "")
                    if "webdynpro" in src.lower() or "ZSVKM" in src.upper():
                        iframe = fr
                        break

            if iframe:
                src = iframe["src"]
                if not src.startswith("http"):
                    src = urljoin(str(resp.url), src)
                resp2 = self._client.get(src)
                self._frame_url = str(resp2.url)
                self._wd_html = resp2.text
            else:
                # Log full response for diagnosis
                all_iframes = soup2.find_all(["iframe", "frame"])
                logger.info(
                    "WebDynpro GET did not land on attendance app. "
                    "iframes=%s  url=%s  html=%r",
                    [fr.get("src", "")[:80] for fr in all_iframes],
                    str(resp.url)[:120],
                    resp.text[:600],
                )
                raise RuntimeError(
                    "Could not reach the attendance WebDynpro app. "
                    "The portal may require additional navigation — please try again."
                )

        self._parse_wd_state(self._wd_html)
        logger.info("Attendance frame loaded: %s", self._frame_url[:80])

    # ── WebDynpro state parsing ──────────────────────────────────────────────

    def _parse_wd_state(self, html: str) -> None:
        """Extract sap-wd-secure-id and fesrAppName from full HTML."""
        soup = BeautifulSoup(html, "lxml")
        sid = soup.find("input", {"name": "sap-wd-secure-id"})
        if sid and sid.get("value"):
            self._secure_id = sid["value"]
        app = soup.find("input", {"name": "fesrAppName"})
        if app and app.get("value"):
            self._app_name = app["value"]

    def _update_secure_id(self, delta: str) -> None:
        """Update sap-wd-secure-id from a delta response (HTML fragment or JS)."""
        # Try HTML input element first
        m = re.search(
            r'name=["\']sap-wd-secure-id["\'][^>]*value=["\']([^"\']+)["\']',
            delta,
        )
        if not m:
            m = re.search(
                r'value=["\']([^"\']+)["\'][^>]*name=["\']sap-wd-secure-id["\']',
                delta,
            )
        if m:
            self._secure_id = m.group(1)

    # ── SAPEVENTQUEUE POST ───────────────────────────────────────────────────

    def post_event(self, sapeventqueue: str) -> str:
        """POST a SAPEVENTQUEUE to the WebDynpro frame. Returns response text."""
        resp = self._client.post(
            self._frame_url,
            data={
                "sap-charset": "utf-8",
                "sap-wd-secure-id": self._secure_id,
                "fesrAppName": self._app_name,
                "SAPEVENTQUEUE": sapeventqueue,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        text = resp.text
        self._update_secure_id(text)
        return text

    # ── DOM parsers (work on full HTML or delta fragments) ───────────────────

    @staticmethod
    def parse_year_options(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        items = soup.select("#WD2C .lsListbox__value")
        result = []
        for el in items:
            label = el.get_text(strip=True)
            label = re.sub(r"^Acad\.?\s*Year\s*", "", label, flags=re.I).strip()
            result.append({
                "id":    el.get("id", ""),
                "key":   el.get("data-itemkey", ""),
                "label": label,
            })
        return result

    @staticmethod
    def parse_sem_options(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        items = soup.select("#WD35 .lsListbox__value")
        if not items:
            items = [
                el for el in soup.select(".lsListbox__value")
                if re.search(r"semester", el.get_text(), re.I)
            ]
        return [
            {
                "id":    el.get("id", ""),
                "key":   el.get("data-itemkey", ""),
                "label": el.get_text(strip=True),
            }
            for el in items
        ]

    @staticmethod
    def get_cb_ids(html: str) -> list[str]:
        """Return IDs of all WD ComboBox inputs (input[ct='CB']) in document order."""
        soup = BeautifulSoup(html, "lxml")
        return [
            el["id"]
            for el in soup.select("input[ct='CB']")
            if el.get("id", "").startswith("WD")
        ]

    @staticmethod
    def get_date_input_ids(html: str) -> list[str]:
        """Return IDs of WD date inputs (input[ct='I'])."""
        soup = BeautifulSoup(html, "lxml")
        ids = [el["id"] for el in soup.select("input[ct='I']") if el.get("id", "").startswith("WD")]
        if not ids:
            ids = [
                el["id"]
                for el in soup.select("input[type='text']")
                if el.get("id", "").startswith("WD") and el.get("offsetParent") != "null"
            ]
        return ids

    @staticmethod
    def get_submit_id(html: str):
        soup = BeautifulSoup(html, "lxml")
        el = soup.find(id="WD52")
        if el:
            return "WD52"
        # Last [ct='B'] element with a WD id
        btns = [
            e for e in soup.select("[ct='B']")
            if e.get("id", "").startswith("WD")
        ]
        return btns[-1]["id"] if btns else None

    @staticmethod
    def parse_pdf_url(html: str):
        soup = BeautifulSoup(html, "lxml")
        obj = (
            soup.find("object", attrs={"ct": "PDF"}) or
            soup.find("object", attrs={"type": "application/pdf"}) or
            soup.find("embed", attrs={"type": "application/pdf"})
        )
        if obj:
            return obj.get("data") or obj.get("src")
        # Regex fallback for SAP delta JS text
        m = re.search(
            r'(?:data|src)=["\']([^"\']+\.pdf[^"\']*)["\']',
            html,
            re.I,
        )
        return m.group(1) if m else None

    # ── PDF download ─────────────────────────────────────────────────────────

    def fetch_bytes(self, url: str):
        try:
            resp = self._client.get(url, timeout=30.0)
            if resp.status_code == 200:
                body = resp.content
                ct = resp.headers.get("content-type", "")
                if "pdf" in ct.lower() or body[:4] == b"%PDF":
                    logger.info("PDF fetched (%d bytes)", len(body))
                    return body
                logger.warning("Response is not PDF (ct=%r, first4=%r)", ct, body[:4])
            else:
                logger.warning("PDF fetch returned HTTP %d", resp.status_code)
        except Exception as exc:
            logger.warning("PDF fetch failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_attendance_options(sap_id: str, sap_password: str) -> dict:
    """
    Log into SAP NetWeaver and return available academic years and semesters.

    Returns:
        {
          "years": [{"key": "2025", "label": "2025-2026"}, ...],
          "semesters": [{"label": "Semester V"}, ...],
          "semesters_by_year": {"2025": [...], ...},
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

    with _SapSession() as sess:
        sess.login(sap_id, sap_password)
        sess.navigate_to_attendance()

        year_opts = sess.parse_year_options(sess._wd_html)
        if not year_opts:
            raise RuntimeError(
                "No academic year options found in attendance form. "
                "The portal layout may have changed — please try again."
            )

        cb_ids = sess.get_cb_ids(sess._wd_html)
        year_cb_id = cb_ids[0] if cb_ids else "WD2B"

        semesters_by_year: dict[str, list] = {}
        for yr in year_opts:
            if not yr["key"]:
                continue
            evt = (
                f"ComboBox_Select~E002Id~E004{year_cb_id}"
                f"~E005Key~E004{yr['key']}"
                f"~E005ByEnter~E004false~E003"
                + _WD_DELTA_SUFFIX
            )
            delta = sess.post_event(evt)
            sems = sess.parse_sem_options(delta)
            semesters_by_year[yr["key"]] = sems
            logger.info(
                "Year %s → %d semesters: %s",
                yr["label"], len(sems), [s["label"] for s in sems],
            )

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
            "semesters":         sem_opts,
            "default_year":      default_year,
            "default_semester":  default_sem,
        }


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

    with _SapSession() as sess:
        sess.login(sap_id, sap_password)
        sess.navigate_to_attendance()

        year_opts = sess.parse_year_options(sess._wd_html)
        if not year_opts:
            raise RuntimeError(
                "No academic year options found in attendance form. "
                "The portal layout may have changed — please try again."
            )

        cb_ids = sess.get_cb_ids(sess._wd_html)
        year_cb_id = cb_ids[0] if cb_ids else "WD2B"
        sem_cb_id  = cb_ids[1] if len(cb_ids) > 1 else "WD33"

        # ── Select academic year ──────────────────────────────────────────
        target_year = (
            next((y for y in year_opts if y["key"] == year_key), None)
            if year_key else None
        )
        if not target_year:
            target_year = year_opts[-1]

        evt = (
            f"ComboBox_Select~E002Id~E004{year_cb_id}"
            f"~E005Key~E004{target_year['key']}"
            f"~E005ByEnter~E004false~E003"
            + _WD_DELTA_SUFFIX
        )
        delta = sess.post_event(evt)
        logger.info("Selected year key=%s", target_year["key"])

        # ── Select semester ───────────────────────────────────────────────
        sem_opts = sess.parse_sem_options(delta)
        if not sem_opts:
            raise RuntimeError(
                "Semester dropdown did not populate after selecting Academic Year. "
                "The portal backend is slow — please try again later."
            )

        target_sem = (
            next((s for s in sem_opts if s["label"] == semester_label), None)
            if semester_label else None
        )
        if not target_sem:
            if semester_label:
                logger.warning(
                    "Semester label %r not found in %s; using last",
                    semester_label, [s["label"] for s in sem_opts],
                )
            target_sem = sem_opts[-1]

        logger.info(
            "Target semester: label=%r key=%r", target_sem["label"], target_sem["key"]
        )

        if target_sem.get("key"):
            evt = (
                f"ComboBox_Select~E002Id~E004{sem_cb_id}"
                f"~E005Key~E004{target_sem['key']}"
                f"~E005ByEnter~E004false~E003"
                + _WD_DELTA_SUFFIX
            )
            delta = sess.post_event(evt)
        else:
            logger.warning("Semester has no data-itemkey; skipping semester POST")

        # ── Select "Detail Report" ────────────────────────────────────────
        # Re-read CB IDs from latest delta (they may shift after semester selection)
        cb_ids_now = sess.get_cb_ids(delta) or cb_ids
        report_cb_id = cb_ids_now[-1] if cb_ids_now else "WD3A"

        # Open report-type dropdown: POST empty key to get the listbox options
        evt_open = (
            f"ComboBox_Select~E002Id~E004{report_cb_id}"
            f"~E005Key~E004"
            f"~E005ByEnter~E004false~E003"
            + _WD_DELTA_SUFFIX
        )
        delta2 = sess.post_event(evt_open)

        soup_detail = BeautifulSoup(delta2, "lxml")
        detail_item = next(
            (
                el for el in soup_detail.select(".lsListbox__value")
                if re.search(r"detail", el.get_text(), re.I)
            ),
            None,
        )

        if detail_item and detail_item.get("data-itemkey"):
            evt_detail = (
                f"ComboBox_Select~E002Id~E004{report_cb_id}"
                f"~E005Key~E004{detail_item['data-itemkey']}"
                f"~E005ByEnter~E004false~E003"
                + _WD_DELTA_SUFFIX
            )
            delta = sess.post_event(evt_detail)
            logger.info(
                "Selected Detail Report (id=%s key=%s)",
                detail_item.get("id"), detail_item["data-itemkey"],
            )
        else:
            logger.warning(
                "Detail Report item not found in dropdown — proceeding with last delta"
            )
            delta = delta2

        # ── Fill date range ───────────────────────────────────────────────
        resolved_start = start_date or _AY_START_DATE
        resolved_end   = end_date or datetime.now(_IST).strftime("%d.%m.%Y")

        # Poll for date inputs to appear (SAP AJAX may be slow)
        date_ids: list[str] = []
        for attempt in range(10):
            date_ids = sess.get_date_input_ids(delta)
            if len(date_ids) >= 2:
                break
            if attempt < 9:
                time.sleep(1)
                # Re-fetch the frame to get updated state
                resp = sess._client.get(sess._frame_url)
                delta = resp.text
                sess._update_secure_id(delta)

        if len(date_ids) >= 2:
            start_id, end_id = date_ids[0], date_ids[1]
            evt_start = (
                f"InputField_Change~E002Id~E004{start_id}"
                f"~E005NewValue~E004{resolved_start}"
                f"~E005~E003"
                + _WD_DELTA_SUFFIX
            )
            delta = sess.post_event(evt_start)
            evt_end = (
                f"InputField_Change~E002Id~E004{end_id}"
                f"~E005NewValue~E004{resolved_end}"
                f"~E005~E003"
                + _WD_DELTA_SUFFIX
            )
            delta = sess.post_event(evt_end)
            logger.info(
                "Filled date range %s → %s (fields: %s, %s)",
                resolved_start, resolved_end, start_id, end_id,
            )
        else:
            logger.warning(
                "Date inputs not found (%d ct='I' WD inputs) — submitting without dates",
                len(date_ids),
            )

        # ── Submit ────────────────────────────────────────────────────────
        submit_id = sess.get_submit_id(delta)
        logger.info("Submit button id=%s", submit_id)
        if not submit_id:
            raise RuntimeError(
                "Submit button not found in the attendance form. "
                "The portal layout may have changed — please try again."
            )

        evt_submit = (
            f"Button_Press~E002Id~E004{submit_id}~E003"
            + _WD_DELTA_SUFFIX
        )
        delta = sess.post_event(evt_submit)
        logger.info("Submit POSTed — polling for PDF object...")

        # ── Poll for PDF URL ──────────────────────────────────────────────
        pdf_url = sess.parse_pdf_url(delta)
        for _ in range(15):   # up to 30 s
            if pdf_url:
                break
            time.sleep(2)
            resp = sess._client.get(sess._frame_url)
            delta = resp.text
            sess._update_secure_id(delta)
            pdf_url = sess.parse_pdf_url(delta)

        if not pdf_url:
            # Diagnostic log
            soup_diag = BeautifulSoup(delta, "lxml")
            logger.warning(
                "POST-SUBMIT DIAGNOSTIC: body_text=%r frames=%r",
                soup_diag.get_text()[:400],
                [str(sess._frame_url)],
            )
            raise RuntimeError(
                "Attendance PDF did not load after form submission. "
                "The report server may be slow — please try again."
            )

        # Resolve relative URLs
        if not pdf_url.startswith("http"):
            pdf_url = urljoin(sess._frame_url, pdf_url)

        logger.info("PDF object found: %s", pdf_url[:100])
        pdf_bytes = sess.fetch_bytes(pdf_url)

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


# ---------------------------------------------------------------------------
# PDF parsing (unchanged from Playwright version)
# ---------------------------------------------------------------------------

# Matches elective category prefixes: "OE-III ", "DE-II ", etc.
_ELECTIVE_PFX_RE = re.compile(r"^[A-Z]{1,4}-\s*(?:[IVX]+|\d+)\s+", re.IGNORECASE)


def _normalize(name: str) -> str:
    """Strip elective prefix, lowercase, replace non-alphanumeric with space."""
    name = _ELECTIVE_PFX_RE.sub("", name)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", name.lower())).strip()


def _enrich_with_course_hours(subjects: list[dict]) -> list[dict]:
    """
    Load course_durations.json and add two computed fields to each subject:

        pending    = course_total_hours − total_conducted
        to_attend  = ceil(0.80 × course_total_hours) − attended
                     (clamped to 0 if already met)
    """
    if not COURSE_DURATIONS_PATH.exists():
        logger.warning("course_durations.json not found — skipping pending/to_attend enrichment")
        for s in subjects:
            s["pending"] = None
            s["to_attend"] = None
        return subjects

    with open(COURSE_DURATIONS_PATH, encoding="utf-8") as f:
        durations = json.load(f)

    dur_map: dict[str, int] = {_normalize(d["course"]): d["total_hours"] for d in durations}

    # Overlay user-submitted hours from Supabase
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
        if norm in dur_map:
            return dur_map[norm]
        for key, hours in dur_map.items():
            if norm in key or key in norm:
                ratio = min(len(norm), len(key)) / max(len(norm), len(key))
                if ratio >= 0.6:
                    return hours
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
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    lines: list[str] = []
    for pg in doc:
        lines.extend(pg.get_text().split("\n"))

    _sr_re = re.compile(r"^\d+$")
    records: list[tuple[str, str, str]] = []
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
    _elective_pfx_re = re.compile(r"^[A-Z]{1,4}-\s*(?:[IVX]+|\d+)\s+", re.IGNORECASE)

    def clean_name(raw: str) -> str:
        name = _elective_pfx_re.sub("", raw)
        name = _suffix_re.sub("", name)
        return name.strip()

    _STOP_WORDS = {"of", "for", "to", "in", "and", "the", "with", "a", "an",
                   "by", "at", "into", "on", "from"}

    def course_key(name: str) -> str:
        words = [w for w in name.lower().split() if w not in _STOP_WORDS]
        if not words:
            return name.lower()
        key = words[0]
        if len(words) > 1:
            key += "_" + words[1][:4]
        return key

    counts: dict[str, dict] = defaultdict(
        lambda: {"present": 0, "total": 0, "not_updated": 0, "display": "", "last_dt": None, "last_str": ""}
    )

    _date_re = re.compile(r"^(\w+)\s+(\d+),\s+(\d{4})$")

    def _parse_date(date_str: str):
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
        dt = _parse_date(date_str)
        if dt and (c["last_dt"] is None or dt > c["last_dt"]):
            c["last_dt"] = dt
            c["last_str"] = dt.strftime("%-d %b %Y")
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
