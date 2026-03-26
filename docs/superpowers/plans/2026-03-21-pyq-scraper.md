# PYQ Scraper & Google Drive Sync — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Playwright scraper that logs into the SVKM portal, downloads all question papers, and syncs them to a structured Google Drive folder.

**Architecture:** Three standalone scripts — `pyq_scraper.py` (portal automation), `drive_uploader.py` (Drive API), `sync_pyqs.py` (orchestrator). All paths flow through `backend/config.py`. Both scraper and uploader are idempotent: re-running skips already-done work.

**Tech Stack:** Playwright (sync API), Google Drive API v3 (`google-api-python-client`), python-dotenv, pytest with mocks for unit tests.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/config.py` | Add `PYQ_DIR`, `SVKM_USERNAME`, `SVKM_PASSWORD`, `GOOGLE_DRIVE_FOLDER_NAME` |
| Modify | `requirements.txt` | Add playwright, google-api-python-client, google-auth-httplib2, google-auth-oauthlib |
| Create | `scripts/__init__.py` | Makes `scripts/` importable as a package for tests |
| Create | `scripts/inspect_portal.py` | One-off headful browser to discover DOM selectors (removed after Task 3) |
| Create | `scripts/pyq_scraper.py` | Playwright login → navigate → scrape → download |
| Create | `scripts/drive_uploader.py` | OAuth2 auth → create folder tree → upload PDFs |
| Create | `scripts/sync_pyqs.py` | Orchestrate scraper + uploader, print summary, exit code |
| Create | `tests/test_drive_uploader.py` | Unit tests for folder caching, skip logic, upload |
| Create | `tests/test_sync_pyqs.py` | Unit tests for orchestrator exit code, summary output |

---

## Task 1: Dependencies + Config

**Files:**
- Modify: `requirements.txt`
- Modify: `backend/config.py`

- [ ] **Step 1.1: Add packages to `requirements.txt`**

Append to `requirements.txt`:
```
# PYQ Scraper
playwright==1.49.1
google-api-python-client==2.154.0
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.1
```

- [ ] **Step 1.2: Install new packages**

```bash
pip install playwright==1.49.1 google-api-python-client==2.154.0 google-auth-httplib2==0.2.0 google-auth-oauthlib==1.2.1
playwright install chromium
```

Expected: no errors, packages importable.

- [ ] **Step 1.3: Add PYQ config to `backend/config.py`**

Add after the `DOCS_DIR` line (around line 26):
```python
# PYQ scraper
PYQ_DIR = DATA_DIR / "pyqs"
SVKM_PORTAL_URL = "https://portal.svkm.ac.in/usermgmt/login"
SVKM_USERNAME = os.getenv("SVKM_USERNAME", "")
SVKM_PASSWORD = os.getenv("SVKM_PASSWORD", "")
GOOGLE_DRIVE_FOLDER_NAME = os.getenv("GOOGLE_DRIVE_FOLDER_NAME", "NMIMS PYQs")
GOOGLE_CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
GOOGLE_TOKEN_PATH = PROJECT_ROOT / "token.json"
```

- [ ] **Step 1.4: Verify config loads**

```bash
python -c "from backend.config import PYQ_DIR, SVKM_USERNAME, GOOGLE_DRIVE_FOLDER_NAME; print(PYQ_DIR, SVKM_USERNAME, GOOGLE_DRIVE_FOLDER_NAME)"
```

Expected: prints the path, your username, and `NMIMS PYQs`.

- [ ] **Step 1.5: Create `scripts/__init__.py`**

```bash
touch scripts/__init__.py
```

Then audit every existing script in `scripts/` (extract_pdf.py, chunk_documents.py, build_index.py, verify_api.py) — any code that runs at module level outside a function or `if __name__ == "__main__":` guard will execute when pytest imports the package. Add `if __name__ == "__main__":` guards to any that lack them.

Check for files with no guard at all:
```bash
grep -L "__main__" scripts/*.py
```

Any file listed has no guard — wrap it before continuing.

**Also manually inspect `verify_api.py`** — even though it has an `if __name__ == "__main__":` guard, it has top-level imports of `backend.embeddings` and `backend.llm_client` outside any guard. If it is ever imported transitively during testing it will attempt real Gemini API calls and break the test suite. Confirm nothing in the new scripts imports `verify_api`; if in doubt, move those top-level imports inside the guard as well.

- [ ] **Step 1.6: Commit**

```bash
git add requirements.txt backend/config.py scripts/__init__.py
git commit -m "feat: add PYQ scraper dependencies and config"
```

---

## Task 2: Portal Inspection (Selector Discovery)

**Files:**
- Create: `scripts/inspect_portal.py` *(removed after Task 3)*

- [ ] **Step 2.1: Create `scripts/inspect_portal.py`**

```python
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
```

- [ ] **Step 2.2: Run the inspector and record selectors**

```bash
python scripts/inspect_portal.py
```

Using the browser DevTools (right-click → Inspect), find and write down:
- **SELECTOR_POST_LOGIN** — element only visible after login (e.g. username display, avatar, dashboard heading)
- **SELECTOR_LIBRARY_LINK** — Library link in sidebar
- **SELECTOR_QP_LINK** — Question Papers sub-link
- **SELECTOR_QP_ROW** — each row/item in the papers list
- **SELECTOR_SUBJECT** — subject text within a row
- **SELECTOR_YEAR** — year within a row
- **SELECTOR_SEMESTER** — semester within a row
- **SELECTOR_DOWNLOAD** — download link or button within a row
- **SELECTOR_NEXT_PAGE** — next-page button (set to `None` if there is no pagination)
- **Download mechanism** — is the href a direct PDF URL, a redirect, or a JS click?

- [ ] **Step 2.3: Commit the inspector**

```bash
git add scripts/inspect_portal.py
git commit -m "chore: add portal inspection script for selector discovery"
```

---

## Task 3: Implement `pyq_scraper.py`

**Files:**
- Create: `scripts/pyq_scraper.py`

Replace all `<SELECTOR_*>` placeholders with the selectors found in Task 2.

- [ ] **Step 3.1: Create `scripts/pyq_scraper.py`**

```python
"""
SVKM Portal → local PYQ downloader.
Playwright sync API. Run via sync_pyqs.py or standalone.
"""
import logging
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

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
    """
    parsed = urlparse(url)
    # Try query parameter named 'file' or 'filename' first
    for key in ("file", "filename", "name"):
        val = parse_qs(parsed.query).get(key, [None])[0]
        if val:
            return val.split("/")[-1]
    # Fall back to last path segment
    segment = parsed.path.split("/")[-1]
    if segment and "." in segment:
        return segment
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
    page.click(SELECTOR_LIBRARY_LINK)
    page.click(SELECTOR_QP_LINK)
    page.wait_for_selector(SELECTOR_QP_ROW, timeout=15_000)
    logger.info("Question Papers page loaded")


def _scrape_page(page, counts: dict) -> None:
    """Scrape all rows on the current question papers page."""
    rows = page.query_selector_all(SELECTOR_QP_ROW)
    for row in rows:
        try:
            subject  = _sanitize(row.query_selector(SELECTOR_SUBJECT).inner_text())
            year     = _sanitize(row.query_selector(SELECTOR_YEAR).inner_text())
            semester = _sanitize(row.query_selector(SELECTOR_SEMESTER).inner_text())
            dl_el    = row.query_selector(SELECTOR_DOWNLOAD)
            url      = dl_el.get_attribute("href")

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
                _relogin_and_navigate(page)
                _scrape_page(page, counts)

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
```

- [ ] **Step 3.2: Fill in all selectors**

Replace every `<SELECTOR_*>` with the CSS selectors found during Task 2.
Set `SELECTOR_NEXT_PAGE = None` if there is no pagination.

- [ ] **Step 3.3: Smoke-test against the live portal**

```bash
python scripts/pyq_scraper.py
```

Expected: login success logged, files downloading to `data/pyqs/`. Temporarily set `headless=False` to watch if needed.

- [ ] **Step 3.4: Verify folder structure**

```bash
find data/pyqs -name "*.pdf" | head -20
```

Expected: `data/pyqs/<Subject>/<Year>/<Semester>/<filename>.pdf`

- [ ] **Step 3.5: Remove the inspector script (no longer needed)**

```bash
git rm scripts/inspect_portal.py
```

- [ ] **Step 3.6: Commit**

```bash
git add scripts/pyq_scraper.py
git commit -m "feat: implement SVKM portal scraper with Playwright"
```

---

## Task 4: Implement `drive_uploader.py`

**Files:**
- Create: `scripts/drive_uploader.py`
- Create: `tests/test_drive_uploader.py`

- [ ] **Step 4.1: Write failing tests**

Create `tests/test_drive_uploader.py`:

```python
"""Unit tests for drive_uploader. Mocks the Drive API — no real network calls."""
from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest

import scripts.drive_uploader as uploader_module
from scripts.drive_uploader import get_or_create_folder, upload_file


@pytest.fixture(autouse=True)
def clear_folder_cache():
    """Clear the in-memory folder ID cache before every test."""
    uploader_module._folder_cache.clear()
    yield
    uploader_module._folder_cache.clear()


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {"files": []}
    svc.files.return_value.create.return_value.execute.return_value = {"id": "new-folder-id"}
    return svc


def test_get_or_create_folder_creates_when_missing(mock_service):
    folder_id = get_or_create_folder(mock_service, "Test Folder", parent_id="root")
    assert folder_id == "new-folder-id"
    mock_service.files.return_value.create.assert_called_once()


def test_get_or_create_folder_reuses_existing(mock_service):
    mock_service.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "existing-id", "name": "Test Folder"}]
    }
    folder_id = get_or_create_folder(mock_service, "Test Folder", parent_id="root")
    assert folder_id == "existing-id"
    mock_service.files.return_value.create.assert_not_called()


def test_folder_id_cache_prevents_duplicate_api_calls(mock_service):
    mock_service.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "cached-id", "name": "Cached Folder"}]
    }
    get_or_create_folder(mock_service, "Cached Folder", parent_id="root")
    get_or_create_folder(mock_service, "Cached Folder", parent_id="root")
    # list() called once — second call uses cache
    assert mock_service.files.return_value.list.call_count == 1


def test_file_already_in_drive_is_skipped(mock_service, tmp_path):
    mock_service.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "existing-file-id", "name": "exam.pdf"}]
    }
    local_file = tmp_path / "exam.pdf"
    local_file.write_bytes(b"%PDF-fake")
    result = upload_file(mock_service, local_file, folder_id="some-folder")
    assert result == "skipped"
    mock_service.files.return_value.create.assert_not_called()


def test_file_is_uploaded_when_not_in_drive(mock_service, tmp_path):
    mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}
    mock_service.files.return_value.create.return_value.execute.return_value = {"id": "new-file-id"}
    local_file = tmp_path / "exam.pdf"
    local_file.write_bytes(b"%PDF-fake")
    with patch("scripts.drive_uploader.MediaFileUpload"):
        result = upload_file(mock_service, local_file, folder_id="some-folder")
    assert result == "uploaded"
```

- [ ] **Step 4.2: Run tests to confirm they fail**

```bash
pytest tests/test_drive_uploader.py -v
```

Expected: `ImportError` — `drive_uploader` doesn't exist yet.

- [ ] **Step 4.3: Create `scripts/drive_uploader.py`**

```python
"""
Google Drive uploader for PYQ files.
Authenticates via OAuth2 (full drive scope — see spec for rationale).
Creates folder tree, uploads PDFs idempotently.
"""
import logging
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from backend.config import (
    PYQ_DIR,
    GOOGLE_DRIVE_FOLDER_NAME,
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_TOKEN_PATH,
)

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]
_MAX_RETRIES = 3

# In-memory cache: (folder_name, parent_id) → folder_id
_folder_cache: dict[tuple, str] = {}


def _authenticate():
    """Return an authenticated Drive service. Opens browser on first run."""
    creds = None
    if GOOGLE_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not GOOGLE_CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {GOOGLE_CREDENTIALS_PATH}. "
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(GOOGLE_CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)
        GOOGLE_TOKEN_PATH.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, name: str, parent_id: str | None) -> str:
    """
    Return the Drive folder ID for `name` under `parent_id`.
    `parent_id="root"` constrains search to My Drive root.
    Creates the folder if missing. Caches results to avoid redundant API calls.
    """
    cache_key = (name, parent_id)
    if cache_key in _folder_cache:
        return _folder_cache[cache_key]

    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    result = service.files().list(q=query, fields="files(id, name)").execute()
    files = result.get("files", [])

    if files:
        folder_id = files[0]["id"]
    else:
        metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            metadata["parents"] = [parent_id]
        folder = service.files().create(body=metadata, fields="id").execute()
        folder_id = folder["id"]
        logger.info("Created Drive folder: %s", name)

    _folder_cache[cache_key] = folder_id
    return folder_id


def upload_file(service, local_path: Path, folder_id: str) -> str:
    """
    Upload a single PDF to the given Drive folder.
    Skip check is scoped to the target folder (not Drive-wide).
    Retries up to _MAX_RETRIES times on failure.
    Returns 'uploaded', 'skipped', or 'failed'.
    """
    filename = local_path.name
    query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    result = service.files().list(q=query, fields="files(id)").execute()
    if result.get("files"):
        logger.info("Skipping (exists in Drive): %s", filename)
        return "skipped"

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            media = MediaFileUpload(str(local_path), mimetype="application/pdf")
            service.files().create(
                body={"name": filename, "parents": [folder_id]},
                media_body=media,
                fields="id",
            ).execute()
            logger.info("Uploaded: %s", filename)
            return "uploaded"
        except Exception as e:
            logger.warning("Upload failed (attempt %d/%d): %s", attempt, _MAX_RETRIES, e)
            if attempt < _MAX_RETRIES:
                time.sleep(2 ** attempt)

    return "failed"


def run() -> dict:
    """
    Walk PYQ_DIR and upload all PDFs to Google Drive.
    Returns {"uploaded": int, "skipped": int, "failed": int}.
    """
    counts = {"uploaded": 0, "skipped": 0, "failed": 0}
    _folder_cache.clear()

    service = _authenticate()
    # Use parent_id="root" to constrain search to My Drive root (not shared drives)
    root_id = get_or_create_folder(service, GOOGLE_DRIVE_FOLDER_NAME, parent_id="root")

    for pdf in sorted(PYQ_DIR.rglob("*.pdf")):
        # pdf path: PYQ_DIR / Subject / Year / Semester / file.pdf
        relative = pdf.relative_to(PYQ_DIR)
        parts = relative.parts  # (Subject, Year, Semester, filename)

        parent = root_id
        for folder_name in parts[:-1]:
            parent = get_or_create_folder(service, folder_name, parent_id=parent)

        result = upload_file(service, pdf, folder_id=parent)
        counts[result] += 1

    logger.info(
        "Uploader done — uploaded: %d, skipped: %d, failed: %d",
        counts["uploaded"], counts["skipped"], counts["failed"],
    )
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print(run())
```

- [ ] **Step 4.4: Run tests — they should pass now**

```bash
pytest tests/test_drive_uploader.py -v
```

Expected: 5 tests pass.

- [ ] **Step 4.5: Commit**

```bash
git add scripts/drive_uploader.py tests/test_drive_uploader.py
git commit -m "feat: implement Google Drive uploader with folder caching and retry"
```

---

## Task 5: Implement `sync_pyqs.py` (Orchestrator)

**Files:**
- Create: `scripts/sync_pyqs.py`
- Create: `tests/test_sync_pyqs.py`

- [ ] **Step 5.1: Write failing tests**

Create `tests/test_sync_pyqs.py`:

```python
"""Unit tests for the sync_pyqs orchestrator."""
from unittest.mock import patch
import pytest

from scripts.sync_pyqs import main


def test_exit_code_0_when_no_failures():
    with patch("scripts.sync_pyqs.pyq_scraper.run", return_value={"downloaded": 5, "skipped": 0, "failed": 0}), \
         patch("scripts.sync_pyqs.drive_uploader.run", return_value={"uploaded": 5, "skipped": 0, "failed": 0}):
        assert main() == 0


def test_exit_code_1_when_scraper_has_failures():
    with patch("scripts.sync_pyqs.pyq_scraper.run", return_value={"downloaded": 3, "skipped": 0, "failed": 2}), \
         patch("scripts.sync_pyqs.drive_uploader.run", return_value={"uploaded": 3, "skipped": 0, "failed": 0}):
        assert main() == 1


def test_exit_code_1_when_uploader_has_failures():
    with patch("scripts.sync_pyqs.pyq_scraper.run", return_value={"downloaded": 5, "skipped": 0, "failed": 0}), \
         patch("scripts.sync_pyqs.drive_uploader.run", return_value={"uploaded": 3, "skipped": 0, "failed": 2}):
        assert main() == 1


def test_uploader_runs_even_when_scraper_has_failures():
    """Partial sync — uploader must always run regardless of scraper failures."""
    with patch("scripts.sync_pyqs.pyq_scraper.run", return_value={"downloaded": 2, "skipped": 0, "failed": 3}), \
         patch("scripts.sync_pyqs.drive_uploader.run", return_value={"uploaded": 2, "skipped": 0, "failed": 0}) as mock_uploader:
        main()
        mock_uploader.assert_called_once()
```

- [ ] **Step 5.2: Run tests to confirm they fail**

```bash
pytest tests/test_sync_pyqs.py -v
```

Expected: `ImportError` — `sync_pyqs` doesn't exist yet.

- [ ] **Step 5.3: Create `scripts/sync_pyqs.py`**

```python
"""
PYQ sync orchestrator.
Runs: SVKM portal scraper → Google Drive uploader.
Usage: python scripts/sync_pyqs.py
Exit code: 0 = all success, 1 = any failures.
"""
import logging
import sys
from scripts import pyq_scraper, drive_uploader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    logger.info("=== PYQ Sync started ===")

    scraper_counts = pyq_scraper.run()
    print(
        f"\nScraper:  {scraper_counts['downloaded']} downloaded, "
        f"{scraper_counts['skipped']} skipped, "
        f"{scraper_counts['failed']} failed"
    )

    # Always run uploader — partial sync is better than none
    uploader_counts = drive_uploader.run()
    print(
        f"Uploader: {uploader_counts['uploaded']} uploaded, "
        f"{uploader_counts['skipped']} skipped, "
        f"{uploader_counts['failed']} failed"
    )

    any_failures = scraper_counts["failed"] > 0 or uploader_counts["failed"] > 0
    exit_code = 1 if any_failures else 0
    logger.info("=== PYQ Sync complete (exit %d) ===", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5.4: Run tests — they should pass now**

```bash
pytest tests/test_sync_pyqs.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5.5: Run full test suite**

```bash
pytest -v
```

Expected: all existing backend tests still pass, plus 9 new tests (5 in test_drive_uploader.py + 4 in test_sync_pyqs.py).

- [ ] **Step 5.6: Commit**

```bash
git add scripts/sync_pyqs.py tests/test_sync_pyqs.py
git commit -m "feat: implement PYQ sync orchestrator with exit code semantics"
```

---

## Task 6: End-to-End Smoke Test

- [ ] **Step 6.1: Set up Google OAuth credentials**

1. Go to Google Cloud Console → APIs & Services → Credentials
2. Create an OAuth 2.0 Client ID (Desktop app type)
3. Download JSON → save as `credentials.json` in the project root
4. Enable Google Drive API for your project

- [ ] **Step 6.2: Run the full sync**

```bash
python scripts/sync_pyqs.py
```

First run: browser opens for Google OAuth consent. Log in, grant access. `token.json` is saved automatically.

Expected output:
```
Scraper:  N downloaded, 0 skipped, 0 failed
Uploader: N uploaded, 0 skipped, 0 failed
```

- [ ] **Step 6.3: Verify Drive folder structure**

Open Google Drive and confirm `NMIMS PYQs / Subject / Year / Semester / *.pdf` exists.

- [ ] **Step 6.4: Re-run to verify idempotency**

```bash
python scripts/sync_pyqs.py
```

Expected: all `skipped`, exit code 0.

- [ ] **Step 6.5: Final commit**

```bash
git add .
git commit -m "feat: PYQ scraper + Drive uploader pipeline complete"
```
