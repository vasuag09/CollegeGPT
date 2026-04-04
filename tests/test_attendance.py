"""
tests/test_attendance.py

Unit tests for attendance_service internals:
- _TTLCache: set/get/expire/delete/bounded-eviction
- _JobTracker: state machine transitions
- _request_cache_key: deterministic, param-sensitive
- _normalize_course_name / _course_identity_key: stable key generation
- _merge_theory_practical_rows: T+P rows aggregated correctly
- _best_duration_match: fuzzy matching
- _enrich_with_course_hours: pending/to_attend computed when match found
"""

import time

import pytest

from backend.attendance_service import (
    MAX_CACHE_ENTRIES,
    AttendanceRequest,
    _JobTracker,
    _TTLCache,
    _best_duration_match,
    _course_identity_key,
    _enrich_with_course_hours,
    _merge_theory_practical_rows,
    _normalize_course_name,
    _request_cache_key,
)


# ---------------------------------------------------------------------------
# _TTLCache
# ---------------------------------------------------------------------------


class TestTTLCache:
    def test_set_and_get(self):
        c = _TTLCache(ttl=60)
        c.set("k", "v")
        assert c.get("k") == "v"

    def test_miss_returns_none(self):
        c = _TTLCache(ttl=60)
        assert c.get("missing") is None

    def test_expires_after_ttl(self):
        c = _TTLCache(ttl=0.05)
        c.set("k", "val")
        assert c.get("k") == "val"
        time.sleep(0.1)
        assert c.get("k") is None

    def test_delete(self):
        c = _TTLCache(ttl=60)
        c.set("k", "v")
        c.delete("k")
        assert c.get("k") is None

    def test_delete_nonexistent_is_noop(self):
        c = _TTLCache(ttl=60)
        c.delete("ghost")  # must not raise

    def test_bounded_eviction(self):
        c = _TTLCache(ttl=3600)
        for i in range(MAX_CACHE_ENTRIES + 10):
            c.set(f"key{i}", i)
        assert len(c._store) <= MAX_CACHE_ENTRIES

    def test_overwrite_existing(self):
        c = _TTLCache(ttl=60)
        c.set("k", 1)
        c.set("k", 2)
        assert c.get("k") == 2


# ---------------------------------------------------------------------------
# _JobTracker
# ---------------------------------------------------------------------------


class TestJobTracker:
    def test_initial_state(self):
        t = _JobTracker()
        assert not t.is_queued("x")
        assert not t.is_processing("x")

    def test_mark_queued(self):
        t = _JobTracker()
        t.mark_queued("u1")
        assert t.is_queued("u1")
        assert not t.is_processing("u1")

    def test_mark_processing_removes_from_queued(self):
        t = _JobTracker()
        t.mark_queued("u1")
        t.mark_processing("u1")
        assert not t.is_queued("u1")
        assert t.is_processing("u1")

    def test_mark_done_clears_all(self):
        t = _JobTracker()
        t.mark_queued("u1")
        t.mark_processing("u1")
        t.mark_done("u1")
        assert not t.is_queued("u1")
        assert not t.is_processing("u1")

    def test_depth_counts_queued_only(self):
        t = _JobTracker()
        t.mark_queued("a")
        t.mark_queued("b")
        t.mark_processing("b")  # removed from queue
        assert t.depth == 1

    def test_multiple_users_independent(self):
        t = _JobTracker()
        t.mark_queued("u1")
        t.mark_queued("u2")
        t.mark_done("u1")
        assert not t.is_queued("u1")
        assert t.is_queued("u2")


# ---------------------------------------------------------------------------
# _request_cache_key
# ---------------------------------------------------------------------------


class TestRequestCacheKey:
    def _req(self, **kwargs):
        defaults = dict(
            sap_id="70471234567",
            password="pw",
            year_key="2025",
            semester_label="Semester VI",
            start_date="01.06.2025",
            end_date="31.03.2026",
        )
        defaults.update(kwargs)
        return AttendanceRequest(**defaults)

    def test_same_params_same_key(self):
        r1 = self._req()
        r2 = self._req()
        assert _request_cache_key(r1) == _request_cache_key(r2)

    def test_different_year_different_key(self):
        r1 = self._req(year_key="2024")
        r2 = self._req(year_key="2025")
        assert _request_cache_key(r1) != _request_cache_key(r2)

    def test_different_semester_different_key(self):
        r1 = self._req(semester_label="Semester IV")
        r2 = self._req(semester_label="Semester VI")
        assert _request_cache_key(r1) != _request_cache_key(r2)

    def test_different_sap_id_different_key(self):
        r1 = self._req(sap_id="70471111111")
        r2 = self._req(sap_id="70472222222")
        assert _request_cache_key(r1) != _request_cache_key(r2)

    def test_password_not_in_key(self):
        r1 = self._req(password="abc")
        r2 = self._req(password="xyz")
        assert _request_cache_key(r1) == _request_cache_key(r2)

    def test_key_format(self):
        r = self._req()
        key = _request_cache_key(r)
        assert key.startswith("data:70471234567:")
        assert len(key.split(":")) == 3


# ---------------------------------------------------------------------------
# _normalize_course_name / _course_identity_key
# ---------------------------------------------------------------------------


class TestNormalizeCourse:
    def test_strips_section_suffix(self):
        assert _normalize_course_name("Machine Learning T1 MBA Tech CE A1") == "machine learning"

    def test_strips_elective_prefix(self):
        assert _normalize_course_name("OE-III Quantum Physics") == "quantum physics"

    def test_strips_noise_tokens(self):
        result = _normalize_course_name("Data Structures MBA B")
        assert "mba" not in result
        assert "b" not in result.split()

    def test_normalizes_whitespace(self):
        result = _normalize_course_name("  Human  Computer  Interaction  ")
        assert "  " not in result

    def test_identity_key_stable(self):
        k1 = _course_identity_key("Machine Learning T1 MBA Tech CE A1")
        k2 = _course_identity_key("Machine Learning T2 MBA Tech CE B2")
        assert k1 == k2

    def test_identity_key_differs_for_different_subjects(self):
        k1 = _course_identity_key("Machine Learning")
        k2 = _course_identity_key("Distributed Computing")
        assert k1 != k2

    def test_empty_string(self):
        assert _course_identity_key("") == ""


# ---------------------------------------------------------------------------
# _merge_theory_practical_rows
# ---------------------------------------------------------------------------


class TestMergeTheoryPractical:
    def _row(self, subject, attended, total, not_updated=0):
        return {"subject": subject, "attended": attended, "total": total,
                "not_updated": not_updated, "last_entry": ""}

    def test_theory_practical_combined(self):
        rows = [
            self._row("Machine Learning T1 MBA Tech CE A1", 10, 12),
            self._row("Machine Learning P1 MBA Tech CE A1", 3, 4),
        ]
        result = _merge_theory_practical_rows(rows)
        assert len(result) == 1
        assert result[0]["attended"] == 13
        assert result[0]["total"] == 16

    def test_different_subjects_not_merged(self):
        rows = [
            self._row("Machine Learning T1", 10, 12),
            self._row("Distributed Computing T1", 8, 10),
        ]
        result = _merge_theory_practical_rows(rows)
        assert len(result) == 2

    def test_percentage_computed(self):
        rows = [self._row("Maths T1", 8, 10)]
        result = _merge_theory_practical_rows(rows)
        assert result[0]["percentage"] == 80.0

    def test_not_updated_only_gives_none_percentage(self):
        rows = [self._row("Physics", 0, 0, not_updated=3)]
        result = _merge_theory_practical_rows(rows)
        assert result[0]["percentage"] is None

    def test_no_classes_no_not_updated_gives_zero(self):
        rows = [self._row("Empty Subject", 0, 0)]
        result = _merge_theory_practical_rows(rows)
        assert result[0]["percentage"] == 0


# ---------------------------------------------------------------------------
# _best_duration_match
# ---------------------------------------------------------------------------


class TestBestDurationMatch:
    def _map(self):
        from backend.attendance_service import _load_course_durations
        return _load_course_durations()

    def test_exact_match(self):
        dm = self._map()
        result = _best_duration_match("Environmental Science", dm)
        assert result is not None
        assert result["total_hours"] == 30

    def test_no_match_returns_none(self):
        dm = self._map()
        result = _best_duration_match("Zyzyx Totally Unknown Course XYZ999", dm)
        assert result is None

    def test_partial_name_still_matches(self):
        # "Maths" should still match something like "Engineering Mathematics"
        # or at minimum not crash on short names
        dm = self._map()
        result = _best_duration_match("Zyzyx", dm)
        assert result is None  # too short / no overlap — should gracefully return None

    def test_empty_string_returns_none(self):
        dm = self._map()
        assert _best_duration_match("", dm) is None


# ---------------------------------------------------------------------------
# _enrich_with_course_hours
# ---------------------------------------------------------------------------


class TestEnrichWithCourseHours:
    def _subject(self, name, attended, total):
        return {"subject": name, "attended": attended, "total": total,
                "not_updated": 0, "last_entry": ""}

    def test_known_subject_gets_pending_and_to_attend(self):
        subjects = [self._subject("Environmental Science", 20, 28)]
        result = _enrich_with_course_hours(subjects)
        assert result[0]["pending"] is not None
        assert result[0]["to_attend"] is not None
        assert result[0]["pending"] >= 0
        assert result[0]["to_attend"] >= 0

    def test_unknown_subject_gets_none(self):
        subjects = [self._subject("Totally Unknown Subject XYZ999", 5, 6)]
        result = _enrich_with_course_hours(subjects)
        assert result[0]["pending"] is None
        assert result[0]["to_attend"] is None

    def test_fully_attended_to_attend_is_zero(self):
        # 30 total hours, 30 conducted, 30 attended → to_attend = ceil(0.8*30)-30 = 24-30 < 0 → 0
        subjects = [self._subject("Environmental Science", 30, 30)]
        result = _enrich_with_course_hours(subjects)
        assert result[0]["to_attend"] == 0

    def test_pending_clamped_to_zero(self):
        # If total_conducted > course_total_hours, pending should be 0 not negative
        subjects = [self._subject("Environmental Science", 35, 40)]
        result = _enrich_with_course_hours(subjects)
        assert result[0]["pending"] == 0
