"""
Google Drive uploader for PYQ files.
Authenticates via OAuth2 (full drive scope — see spec for rationale).
Creates folder tree, uploads PDFs idempotently.
"""
import logging
import time
from pathlib import Path
from typing import Optional

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


def get_or_create_folder(service, name: str, parent_id: Optional[str]) -> str:
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
