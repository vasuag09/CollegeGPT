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
    ↓  (Playwright browser automation)
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
GOOGLE_DRIVE_FOLDER_NAME=NMIMS PYQs
```

Google OAuth2 credentials stored in `credentials.json` (downloaded once from Google Cloud Console).
Token cached in `token.json` after first OAuth flow — subsequent runs are non-interactive.

---

## Module 1: `pyq_scraper.py`

**Responsibilities:** Authenticate with the portal, scrape all question paper entries, download PDFs.

### Login Flow
1. Launch headless Playwright Chromium browser
2. Navigate to `https://portal.svkm.ac.in/usermgmt/login`
3. Fill `SVKM_USERNAME` and `SVKM_PASSWORD` from environment
4. Submit form and wait for successful redirect

### Navigation
1. Click "Library" in the sidebar
2. Click "Question Papers"
3. Wait for the question paper list to fully render

### Scraping
- Papers appear as a list on the page
- For each entry, extract:
  - Subject name
  - Year
  - Semester
  - File download link
- Handle pagination if multiple pages exist

### Download
- Local path: `data/pyqs/<Subject>/<Year>/<Semester>/<filename>.pdf`
- Create intermediate directories as needed
- Skip files that already exist (idempotent)
- Log each download: `✓ Downloaded: Subject/Year/Semester/filename.pdf`

---

## Module 2: `drive_uploader.py`

**Responsibilities:** Authenticate with Google Drive, create folder structure, upload files.

### Authentication
- OAuth2 flow using `credentials.json` (scopes: `https://www.googleapis.com/auth/drive`)
- On first run: opens browser for user consent, saves token to `token.json`
- On subsequent runs: loads token from `token.json` silently

### Folder Management
- Check if root folder `NMIMS PYQs` exists in Drive; create if not
- For each file, recursively ensure `NMIMS PYQs / Subject / Year / Semester` path exists
- Cache folder IDs in memory during the run to avoid redundant API calls

### Upload
- Upload each PDF with MIME type `application/pdf`
- Skip files already present in the target Drive folder (check by filename)
- Log each upload: `✓ Uploaded: Subject/Year/Semester/filename.pdf`

---

## Module 3: `sync_pyqs.py`

**Responsibilities:** Orchestrate the full pipeline end-to-end.

```
1. Load .env credentials
2. Run pyq_scraper → downloads all PYQs to data/pyqs/
3. Run drive_uploader → syncs data/pyqs/ to Google Drive
4. Print summary: X files downloaded, Y uploaded, Z skipped
```

Both modules are idempotent — re-running `sync_pyqs.py` safely skips already-completed work.

---

## Dependencies

New Python packages required:
```
playwright          # Browser automation
google-api-python-client  # Google Drive API
google-auth-httplib2
google-auth-oauthlib
```

Install Playwright browser: `playwright install chromium`

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Login fails (wrong credentials) | Raise error with clear message, abort |
| File download fails | Log warning, skip file, continue |
| Drive upload fails | Log warning, skip file, continue |
| Network timeout | Retry up to 3 times with exponential backoff |
| Session expires mid-scrape | Re-login and retry current page |

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
