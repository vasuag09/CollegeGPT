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


def test_same_folder_name_different_parent_creates_separate_entries(mock_service):
    """Same folder name under different parents must be distinct cache entries."""
    mock_service.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "folder-under-2023", "name": "Semester I"}]
    }
    get_or_create_folder(mock_service, "Semester I", parent_id="parent-2023")

    mock_service.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "folder-under-2024", "name": "Semester I"}]
    }
    get_or_create_folder(mock_service, "Semester I", parent_id="parent-2024")

    # Two distinct parent_ids = two separate API list calls (not cached from first)
    assert mock_service.files.return_value.list.call_count == 2


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
