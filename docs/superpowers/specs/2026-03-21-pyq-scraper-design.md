# PYQ Scraper & Google Drive Sync — Design Spec

**Date:** 2026-03-21
**Status:** Approved
**Author:** Vasu Agrawal

---

## Overview

A standalone scraper pipeline that:
1. Logs into the SVKM student portal using stored credentials
2. Navigates to Library → Question Papers
3. Downloads all PYQ PDFs locally, organized by subject/year/semester
4. Uploads them to a structured Google Drive folder tree

This is independent of the RAG backend — it runs as a one-off (or repeated) sync script.

---

## Architecture

```
scripts/
  pyq_scraper.py      # Playwright: login → navigate → download PYQs locally
  drive_uploader.py   # Google Drive API: create folders → upload files
  sync_pyqs.py        # Orchestrator: runs scraper → uploader end-to-end
```

**Data flow:**
```
SVKM Portal
    ↓  (Playwright sync browser automation)
data/pyqs/<Subject>/<Year>/<Semester>/*.pdf
    ↓  (Google Drive API v3)
NMIMS PYQs/<Subject>/<Year>/<Semester>/*.pdf  (Google Drive)
```

---

## Configuration

Added to `.env`:
```
SVKM_USERNAME=...
SVKM_PASSWORD=...
GOOGLE_DRIVE_FOLDER_NAME=NMIMS PYQs  # default: "NMIMS PYQs" if not set
```

Google OAuth2 credentials stored in `credentials.json` (downloaded once from Google Cloud Console).
Token cached in `token.json` after first OAuth flow — subsequent runs are non-interactive.

**Security — these are code changes, not just notes:**
- `credentials.json`, `token.json`, and `data/pyqs/` are already added to `.gitignore`
- A dedicated service/shared account is strongly preferred over a personal student credential — if the portal locks after repeated failed logins, a personal account will be inaccessible
- The pipeline uses a personal student account for the prototype; switch to a service account before any shared deployment

**Local path** is declared in `backend/config.py` as `PYQ_DIR = DATA_DIR / "pyqs"` alongside existing path constants. `GOOGLE_DRIVE_FOLDER_NAME` defaults to `"NMIMS PYQs"` if the env var is not set, consistent with existing config patterns.

---

## Dependencies

New Python packages to add to `requirements.txt`:
```
playwright
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
```

After installing: `playwright install chromium`

---

## Module 1: `pyq_scraper.py`

**Responsibilities:** Authenticate with the portal, scrape all question paper entries, download PDFs.

**API:** Uses Playwright's **synchronous** API (not async) — this is a standalone script, not integrated with FastAPI's async event loop.

**Returns:** `dict` with keys `downloaded: int`, `skipped: int`, `failed: int`

### Login Flow
1. Launch headless Playwright Chromium browser
2. Navigate to `https://portal.svkm.ac.in/usermgmt/login`
3. Fill `SVKM_USERNAME` and `SVKM_PASSWORD` from environment
4. Submit form
5. Wait for login confirmation via `page.wait_for_selector("<post-login-element>")` — exact selector TBD after inspecting the portal's post-login DOM. Candidates: a sidebar element unique to logged-in state, or `page.wait_for_url("**/home**")`.

**Auth failure:** Raise a clear error and **abort immediately — do not retry**. Repeated failed login attempts may lock the account. The user must fix credentials in `.env` before re-running.

### Navigation
1. Click "Library" in the sidebar
2. Click "Question Papers"
3. Wait for the question paper list to fully render via `page.wait_for_selector("<list-element>")` — selector TBD after portal inspection

### Scraping

> **Note:** Exact CSS selectors and DOM structure are TBD pending inspection of the portal's rendered HTML. The implementation step must begin with a manual inspection session to document selectors before writing scraping code.

For each list entry, extract:
- Subject name
- Year
- Semester
- File download link / download trigger

**Download mechanism** is TBD pending inspection — possibilities:
- Direct PDF URL: use `page.request.get(url)` — **must use `page.request`, not `httpx` or `requests`**, so that authenticated session cookies are carried automatically
- Auth-gated redirect: use Playwright's `page.expect_download()` context
- JavaScript-triggered download: use `page.expect_download()` with a click

**Pagination:** Mechanism is TBD pending inspection (traditional page links, "Load More" button, or infinite scroll each require a different Playwright approach). Flag for investigation during implementation.

### Download
- Local path: `PYQ_DIR / <Subject> / <Year> / <Semester> / <filename>.pdf` (using `config.PYQ_DIR`)
- Create intermediate directories as needed
- Skip files that already exist (idempotent)
- Log each result: `✓ Downloaded: Subject/Year/Semester/filename.pdf` or `⚠ Failed: ...`

---

## Module 2: `drive_uploader.py`

**Responsibilities:** Authenticate with Google Drive, create folder structure, upload files.

**Returns:** `dict` with keys `uploaded: int`, `skipped: int`, `failed: int`

### Authentication
- OAuth2 flow using `credentials.json`
- **Scope:** `https://www.googleapis.com/auth/drive` — full Drive access is required because `drive.file` only covers files created by the current token session; on a fresh token, previously-created folders are invisible, causing duplicate root folders to be silently created. This is a deliberate tradeoff: the script is admin-run, not user-facing.
- On first run: opens browser for user consent, saves token to `token.json`
- On subsequent runs: loads token from `token.json` silently

### Folder Management
- Check if root folder `NMIMS PYQs` exists in Drive root; create if not
- For each file, recursively ensure `NMIMS PYQs / Subject / Year / Semester` path exists
- Cache folder IDs in a `dict` during the run to avoid redundant API calls per upload

### Upload
- Upload each PDF with MIME type `application/pdf`
- Skip check is **scoped to the target `Subject/Year/Semester` folder** — check by filename within that specific folder only
- Log each result: `✓ Uploaded: Subject/Year/Semester/filename.pdf` or `⚠ Failed: ...`

---

## Module 3: `sync_pyqs.py`

**Responsibilities:** Orchestrate the full pipeline end-to-end.

```
1. Load .env credentials
2. Run pyq_scraper → downloads all PYQs to PYQ_DIR
   Returns: {downloaded, skipped, failed}
3. Run drive_uploader regardless of scraper failed count
   (partial sync is better than no sync)
   Returns: {uploaded, skipped, failed}
4. Print summary:
   Scraper:  X downloaded, Y skipped, Z failed
   Uploader: X uploaded, Y skipped, Z failed
5. Exit with code 1 if either module has failed > 0, else exit 0
```

Both modules are idempotent — re-running `sync_pyqs.py` safely skips already-completed work.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Login fails (wrong credentials) | Raise error with clear message, **abort — do not retry** |
| Re-login after session expiry fails | Apply auth failure rule — raise immediately, do not retry |
| Post-login selector not found | Raise error: login may have succeeded but DOM changed |
| File download fails | Log warning, skip file, continue — count in `failed` |
| Drive upload fails | Log warning, skip file, continue — count in `failed` |
| Network timeout | Retry up to 3 times with exponential backoff |
| Session expires mid-scrape | Re-login once and retry current page |

---

## Folder Structure on Google Drive

```
NMIMS PYQs/
  Computer Science/
    2024/
      Semester I/
        CS101_Data_Structures_2024_Sem1.pdf
      Semester II/
        CS201_Algorithms_2024_Sem2.pdf
  Electronics/
    2023/
      Semester I/
        EC101_Circuits_2023_Sem1.pdf
```

---

## Out of Scope

- Integration with the RAG pipeline (separate feature, see roadmap 4.2)
- Scheduled/automatic sync (can be added later via cron)
- Deduplication across years (same paper appearing multiple times)
