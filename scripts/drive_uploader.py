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

# Upload registry — persists across runs so restarts skip already-uploaded files
UPLOAD_REGISTRY_PATH = PYQ_DIR.parent / "pyqs_uploaded.txt"


def load_uploaded_registry() -> set:
    """Return set of relative paths (str) already uploaded to Drive."""
    if UPLOAD_REGISTRY_PATH.exists():
        return set(UPLOAD_REGISTRY_PATH.read_text().splitlines())
    return set()


def mark_as_uploaded(relative_path: str) -> None:
    """Append a relative path to the upload registry."""
    UPLOAD_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(UPLOAD_REGISTRY_PATH, "a") as f:
        f.write(relative_path + "\n")


def authenticate():
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


def upload_and_delete(service, local_path: Path, root_id: str) -> str:
    """
    Upload local_path to Drive (mirroring PYQ_DIR folder structure under root_id),
    then delete the local file on success.
    Returns 'uploaded', 'skipped', or 'failed'.
    """
    relative = local_path.relative_to(PYQ_DIR)
    parts = relative.parts  # e.g. ('B TECH', 'CE', '1ST YEAR', 'I SEMESTER', 'file.pdf')

    parent = root_id
    for folder_name in parts[:-1]:
        parent = get_or_create_folder(service, folder_name, parent_id=parent)

    result = upload_file(service, local_path, folder_id=parent)
    if result in ("uploaded", "skipped"):
        local_path.unlink()
        logger.info("Deleted local copy: %s", relative)
    return result


def get_or_create_folder(service, name: str, parent_id: Optional[str]) -> str:
    """
    Return the Drive folder ID for `name` under `parent_id`.
    `parent_id="root"` constrains search to My Drive root (not shared drives).
    Creates the folder if missing. Caches results. Retries on network errors.
    """
    cache_key = (name, parent_id)
    if cache_key in _folder_cache:
        return _folder_cache[cache_key]

    safe_name = name.replace("'", "\\'")
    query = f"name='{safe_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
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
        except Exception as exc:
            logger.warning("get_or_create_folder attempt %d/%d failed: %s", attempt, _MAX_RETRIES, exc)
            if attempt < _MAX_RETRIES:
                time.sleep(2 ** attempt)

    raise RuntimeError(f"Failed to get/create Drive folder '{name}' after {_MAX_RETRIES} attempts")


def upload_file(service, local_path: Path, folder_id: str) -> str:
    """
    Upload a single PDF to the given Drive folder.
    Skip check is scoped to the target folder (not Drive-wide).
    Both the existence check and the upload are inside the retry loop.
    Returns 'uploaded', 'skipped', or 'failed'.
    """
    filename = local_path.name
    safe_filename = filename.replace("'", "\\'")
    query = f"name='{safe_filename}' and '{folder_id}' in parents and trashed=false"

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            result = service.files().list(q=query, fields="files(id)").execute()
            if result.get("files"):
                logger.info("Skipping (exists in Drive): %s", filename)
                return "skipped"
            media = MediaFileUpload(str(local_path), mimetype="application/pdf")
            service.files().create(
                body={"name": filename, "parents": [folder_id]},
                media_body=media,
                fields="id",
            ).execute()
            logger.info("Uploaded: %s", filename)
            return "uploaded"
        except Exception as e:
            logger.warning("Upload attempt %d/%d failed: %s", attempt, _MAX_RETRIES, e)
            if attempt < _MAX_RETRIES:
                time.sleep(2 ** attempt)

    return "failed"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    service = authenticate()
    root_id = get_or_create_folder(service, GOOGLE_DRIVE_FOLDER_NAME, parent_id="root")
    print(f"Root folder ID: {root_id}")
