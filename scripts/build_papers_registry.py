"""
Build data/question_papers.json from the Google Drive PYQ folder tree.

Walks the NMIMS PYQs Drive folder recursively, classifies each folder segment
as program / year / branch / semester / subject using semantic regex patterns,
and writes a JSON array of paper records with Drive webViewLinks.

Run: python -m scripts.build_papers_registry
"""
import json
import logging
import re

from backend.config import GOOGLE_DRIVE_FOLDER_NAME, PAPERS_REGISTRY_PATH
from scripts.drive_uploader import authenticate, get_or_create_folder

logger = logging.getLogger(__name__)

_MIME_FOLDER = "application/vnd.google-apps.folder"

# Patterns to classify folder name segments
_YEAR_RE = re.compile(r"\d+\s*(ST|ND|RD|TH)\s*YEAR", re.IGNORECASE)
_SEM_RE = re.compile(
    r"(^(I{1,3}V?|VI{0,3}|IX|X)\s*SEM|(SEM|SEMESTER)[-\s]*[\dIVX]+)",
    re.IGNORECASE,
)


def _list_children(service, folder_id: str) -> list[dict]:
    """Return all non-trashed children of folder_id (paginated)."""
    query = f"'{folder_id}' in parents and trashed=false"
    fields = "nextPageToken, files(id, name, mimeType, webViewLink)"
    items = []
    page_token = None
    while True:
        resp = (
            service.files()
            .list(q=query, fields=fields, pageSize=1000, pageToken=page_token)
            .execute()
        )
        items.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return items


def _parse_path(path_parts: list[str], filename: str) -> dict:
    """
    Interpret variable-depth path_parts into structured fields.

    path_parts = folder segments between root and filename, e.g.:
      ["B TECH", "1ST YEAR", "I SEMESTER", "CALCULUS"]          → 4 parts
      ["B TECH", "2ND YEAR", "CE", "SEM-III", "DATA STRUCTURES"] → 5 parts
    """
    record = {
        "program": None,
        "branch": None,
        "year": None,
        "semester": None,
        "subject": None,
        "filename": filename,
        "drive_url": None,  # filled by caller
    }

    if not path_parts:
        record["subject"] = filename.replace(".pdf", "").strip()
        return record

    record["program"] = path_parts[0]

    if len(path_parts) == 1:
        record["subject"] = filename.replace(".pdf", "").strip()
        return record

    # Classify remaining parts
    remaining = path_parts[1:]
    year_idx = next((i for i, p in enumerate(remaining) if _YEAR_RE.search(p)), None)
    sem_idx = next((i for i, p in enumerate(remaining) if _SEM_RE.search(p)), None)

    if year_idx is not None:
        record["year"] = remaining[year_idx]
    if sem_idx is not None:
        record["semester"] = remaining[sem_idx]

    # Subject = last part (if not year or semester)
    last = remaining[-1]
    if not _YEAR_RE.search(last) and not _SEM_RE.search(last):
        record["subject"] = last
    else:
        record["subject"] = filename.replace(".pdf", "").strip()

    # Branch = any part between year and semester that is neither
    classified = set()
    if year_idx is not None:
        classified.add(year_idx)
    if sem_idx is not None:
        classified.add(sem_idx)
    if record["subject"] == remaining[-1]:
        classified.add(len(remaining) - 1)

    branch_parts = [
        p for i, p in enumerate(remaining)
        if i not in classified
        and not _YEAR_RE.search(p)
        and not _SEM_RE.search(p)
        and p != record["subject"]
    ]
    if branch_parts:
        record["branch"] = " / ".join(branch_parts)

    return record


def _walk_folder(
    service, folder_id: str, path_parts: list[str]
) -> list[dict]:
    """Recursively walk folder tree; return list of paper records."""
    children = _list_children(service, folder_id)
    folders = [c for c in children if c["mimeType"] == _MIME_FOLDER]
    files = [c for c in children if c["mimeType"] != _MIME_FOLDER]

    records = []

    for folder in folders:
        records.extend(
            _walk_folder(service, folder["id"], path_parts + [folder["name"]])
        )

    for f in files:
        if not f["name"].lower().endswith(".pdf"):
            continue
        record = _parse_path(path_parts, f["name"])
        record["drive_url"] = f.get("webViewLink", "")
        records.append(record)

    return records


def build_registry() -> None:
    """Walk Drive, build registry, write question_papers.json."""
    service = authenticate()
    root_id = get_or_create_folder(service, GOOGLE_DRIVE_FOLDER_NAME, parent_id="root")
    logger.info("Walking Drive folder '%s' (id=%s)...", GOOGLE_DRIVE_FOLDER_NAME, root_id)

    records = _walk_folder(service, root_id, [])
    logger.info("Found %d papers", len(records))

    PAPERS_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PAPERS_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Written {len(records)} papers to {PAPERS_REGISTRY_PATH}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    build_registry()
