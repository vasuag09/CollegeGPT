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


def test_uploader_still_runs_when_scraper_raises():
    """If scraper raises RuntimeError (e.g. login failure), uploader still runs."""
    with patch("scripts.sync_pyqs.pyq_scraper.run", side_effect=RuntimeError("Login failed")), \
         patch("scripts.sync_pyqs.drive_uploader.run", return_value={"uploaded": 0, "skipped": 0, "failed": 0}) as mock_uploader:
        exit_code = main()
        mock_uploader.assert_called_once()
        assert exit_code == 1  # scraper failure counts as failed > 0
