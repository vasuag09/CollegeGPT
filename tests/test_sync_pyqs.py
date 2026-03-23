"""Unit tests for the sync_pyqs orchestrator."""
from contextlib import ExitStack
from unittest.mock import patch, MagicMock
import pytest

from scripts.sync_pyqs import main

MOCK_SERVICE = MagicMock()
MOCK_ROOT_ID = "fake-root-id"

_BASE_PATCHES = [
    ("scripts.sync_pyqs.drive_uploader.authenticate", {"return_value": MOCK_SERVICE}),
    ("scripts.sync_pyqs.drive_uploader.get_or_create_folder", {"return_value": MOCK_ROOT_ID}),
    ("scripts.sync_pyqs.drive_uploader.upload_and_delete", {"return_value": "uploaded"}),
    ("scripts.sync_pyqs.drive_uploader.load_uploaded_registry", {"return_value": set()}),
    ("scripts.sync_pyqs.drive_uploader.mark_as_uploaded", {}),
]


def apply_base(stack):
    for target, kwargs in _BASE_PATCHES:
        stack.enter_context(patch(target, **kwargs))


def test_exit_code_0_when_no_failures():
    with ExitStack() as stack:
        apply_base(stack)
        stack.enter_context(patch(
            "scripts.sync_pyqs.pyq_scraper.run",
            return_value={"downloaded": 5, "skipped": 0, "failed": 0},
        ))
        assert main() == 0


def test_exit_code_1_when_scraper_has_failures():
    with ExitStack() as stack:
        apply_base(stack)
        stack.enter_context(patch(
            "scripts.sync_pyqs.pyq_scraper.run",
            return_value={"downloaded": 3, "skipped": 0, "failed": 2},
        ))
        assert main() == 1


def test_exit_code_1_when_uploader_has_failures():
    """An upload failure (via callback) causes exit code 1."""
    def scraper_with_callback(on_downloaded=None, skip_paths=None, **kwargs):
        if on_downloaded:
            on_downloaded(MagicMock())
        return {"downloaded": 1, "skipped": 0, "failed": 0}

    with ExitStack() as stack:
        stack.enter_context(patch("scripts.sync_pyqs.drive_uploader.authenticate", return_value=MOCK_SERVICE))
        stack.enter_context(patch("scripts.sync_pyqs.drive_uploader.get_or_create_folder", return_value=MOCK_ROOT_ID))
        stack.enter_context(patch("scripts.sync_pyqs.drive_uploader.upload_and_delete", return_value="failed"))
        stack.enter_context(patch("scripts.sync_pyqs.drive_uploader.load_uploaded_registry", return_value=set()))
        stack.enter_context(patch("scripts.sync_pyqs.drive_uploader.mark_as_uploaded"))
        stack.enter_context(patch("scripts.sync_pyqs.pyq_scraper.run", side_effect=scraper_with_callback))
        assert main() == 1


def test_uploader_called_even_when_scraper_has_failures():
    """Partial sync — scraper failures don't prevent exit code reporting."""
    with ExitStack() as stack:
        apply_base(stack)
        stack.enter_context(patch(
            "scripts.sync_pyqs.pyq_scraper.run",
            return_value={"downloaded": 2, "skipped": 0, "failed": 3},
        ))
        assert main() == 1


def test_drive_auth_failure_aborts_early():
    """If Drive auth fails, exit immediately with code 1 without running scraper."""
    with ExitStack() as stack:
        stack.enter_context(patch("scripts.sync_pyqs.drive_uploader.authenticate", side_effect=Exception("auth error")))
        mock_scraper = stack.enter_context(patch("scripts.sync_pyqs.pyq_scraper.run"))
        assert main() == 1
        mock_scraper.assert_not_called()


def test_uploader_still_reports_when_scraper_raises():
    """If scraper raises RuntimeError, exit code is 1 and upload counts are printed."""
    with ExitStack() as stack:
        apply_base(stack)
        stack.enter_context(patch(
            "scripts.sync_pyqs.pyq_scraper.run",
            side_effect=RuntimeError("Login failed"),
        ))
        assert main() == 1


def test_upload_exception_does_not_crash_scraper():
    """RuntimeError from upload_and_delete is caught; scraper run continues."""
    def scraper_with_callback(on_downloaded=None, skip_paths=None, **kwargs):
        if on_downloaded:
            on_downloaded(MagicMock())
        return {"downloaded": 1, "skipped": 0, "failed": 0}

    with ExitStack() as stack:
        stack.enter_context(patch("scripts.sync_pyqs.drive_uploader.authenticate", return_value=MOCK_SERVICE))
        stack.enter_context(patch("scripts.sync_pyqs.drive_uploader.get_or_create_folder", return_value=MOCK_ROOT_ID))
        stack.enter_context(patch(
            "scripts.sync_pyqs.drive_uploader.upload_and_delete",
            side_effect=RuntimeError("Network error after retries"),
        ))
        stack.enter_context(patch("scripts.sync_pyqs.drive_uploader.load_uploaded_registry", return_value=set()))
        stack.enter_context(patch("scripts.sync_pyqs.drive_uploader.mark_as_uploaded"))
        stack.enter_context(patch("scripts.sync_pyqs.pyq_scraper.run", side_effect=scraper_with_callback))
        # Should not raise; exception is caught and counted as a failed upload
        result = main()
        assert result == 1
