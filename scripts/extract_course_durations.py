"""
NM-GPT – Course Duration Extractor

Reads every unique PDF in the `Course Policy/` directory, extracts subject name,
course code, semester, and total contact hours for each course policy document,
and writes a deduplicated JSON registry to `data/course_durations.json`.

Total contact hours = (Lecture + Practical + Tutorial hours per week) × 15 weeks.

Run:
    python -m scripts.extract_course_durations

Output schema (one object per unique course code):
    {
      "code":          "701ME0C003",
      "course":        "Engineering Drawing",
      "semester":      "I",
      "lecture_hrs":   2,
      "practical_hrs": 2,
      "tutorial_hrs":  0,
      "total_hours":   60,
      "source":        "Semester_-_1_MS9CHxbnM9.pdf"
    }
"""

import hashlib
import json
import logging
import re
import sys

import fitz  # PyMuPDF

from backend.config import COURSE_DURATIONS_PATH, COURSE_POLICY_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_WEEKS = 15

# ── Regexes ────────────────────────────────────────────────────────────────
_COURSE_RE      = re.compile(r"^\s*Course\s*[:/]\s*(.+)", re.IGNORECASE)
_CODE_RE        = re.compile(r"^\s*(?:Code|Module\s+Code)\s*[:/]\s*([A-Z0-9]+)", re.IGNORECASE)
_SEM_RE         = re.compile(r"^\s*Semester\s*[:/]\s*(.+)", re.IGNORECASE)
_TS_RE          = re.compile(r"^\s*Teaching\s+Scheme\s*$", re.IGNORECASE)
_SMALL_INT_RE   = re.compile(r"^\d+$")
_MODULE_PFX_RE  = re.compile(r"^Module\s*[:/]\s*", re.IGNORECASE)

# Stop collecting Teaching Scheme integers once we hit one of these sections
_TS_STOP_RE = re.compile(
    r"^\s*(Course\s+(Objective|Outcome)|Detailed\s+Syllabus|Pre.?requisite|Text\s+Book)",
    re.IGNORECASE,
)

# Words that appear after "Course:" but are NOT course names
_NOISE_WORDS = {"objective", "objectives", "outcome", "outcomes", "policy", "duration"}


def _clean_course_name(raw: str) -> str:
    name = _MODULE_PFX_RE.sub("", raw).strip()
    return " ".join(name.split())


def _is_noise(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in _NOISE_WORDS) or len(name) < 3


def _md5(path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _unique_pdfs(directory) -> list:
    """Return deduplicated PDF paths from directory (unique by MD5)."""
    seen: set[str] = set()
    unique = []
    for pdf in sorted(directory.glob("*.pdf")):
        h = _md5(pdf)
        if h not in seen:
            seen.add(h)
            unique.append(pdf)
    return unique


def _extract_from_pdf(pdf_path) -> list[dict]:
    """
    Parse a single PDF and return all course records found in it.

    For each course policy document the Teaching Scheme table provides:
        Lecture (hrs/week)  Practical (hrs/week)  Tutorial (hrs/week)  Credit

    We collect the first three standalone integers ≤ 20 that appear after the
    "Teaching Scheme" line (the column values), then compute:
        total_hours = (L + P + T) × 15 weeks
    """
    doc = fitz.open(str(pdf_path))
    lines: list[str] = []
    for page in doc:
        lines.extend(page.get_text().split("\n"))

    records: list[dict] = []
    current: dict = {}
    in_ts = False        # inside Teaching Scheme integer-collection window
    ts_ints: list[int] = []

    def _emit():
        """Emit current record if we have enough data."""
        if "course" in current and "code" in current and "lpt" in current:
            L, P, T = current["lpt"]
            records.append({
                "code":          current["code"],
                "course":        current["course"],
                "semester":      current.get("semester", ""),
                "lecture_hrs":   L,
                "practical_hrs": P,
                "tutorial_hrs":  T,
                "total_hours":   (L + P + T) * _WEEKS,
                "source":        pdf_path.name,
            })

    for i, raw in enumerate(lines):
        line = raw.strip()

        # ── Teaching Scheme integer collection ────────────────────
        if in_ts:
            if _TS_STOP_RE.match(line):
                # Reached next section — stop collecting
                in_ts = False
                ts_ints = []
            elif _SMALL_INT_RE.match(line):
                val = int(line)
                if val <= 20:          # L/P/T are always ≤ 10; Credit ≤ ~8
                    ts_ints.append(val)
                if len(ts_ints) >= 3:
                    current["lpt"] = (ts_ints[0], ts_ints[1], ts_ints[2])
                    in_ts = False
                    ts_ints = []
            # continue collecting — skip other matchers while in TS mode
            continue

        # ── Teaching Scheme header ────────────────────────────────
        if _TS_RE.match(line):
            in_ts = True
            ts_ints = []
            continue

        # ── New course block starts when we see Course: after lpt is set ──
        # Emit previous record first if we have one ready
        m = _COURSE_RE.match(line)
        if m:
            name = _clean_course_name(m.group(1))
            if not _is_noise(name):
                # New course starting — emit whatever we had before
                _emit()
                current = {"course": name}
            continue

        # Course code
        m = _CODE_RE.match(line)
        if m:
            current["code"] = m.group(1).strip()
            continue

        # Semester (first match only per block)
        m = _SEM_RE.match(line)
        if m and "semester" not in current:
            current["semester"] = " ".join(m.group(1).split())
            continue

    # Emit the last course in the file
    _emit()

    return records


def build_registry() -> list[dict]:
    """
    Process all unique PDFs in COURSE_POLICY_DIR, deduplicate by course code,
    write JSON to COURSE_DURATIONS_PATH, and return the final list.
    """
    if not COURSE_POLICY_DIR.exists():
        logger.error("Course Policy directory not found: %s", COURSE_POLICY_DIR)
        sys.exit(1)

    pdfs = _unique_pdfs(COURSE_POLICY_DIR)
    logger.info("Processing %d unique PDFs in %s", len(pdfs), COURSE_POLICY_DIR)

    all_records: list[dict] = []
    for pdf in pdfs:
        found = _extract_from_pdf(pdf)
        logger.info("  %s → %d courses", pdf.name, len(found))
        all_records.extend(found)

    logger.info("Total raw records: %d", len(all_records))

    # Deduplicate by code — keep entry with longest course name
    deduped: dict[str, dict] = {}
    for rec in all_records:
        code = rec["code"]
        if code not in deduped or len(rec["course"]) > len(deduped[code]["course"]):
            deduped[code] = rec

    # Sort: semester string, then code
    final = sorted(deduped.values(), key=lambda r: (r["semester"], r["code"]))

    COURSE_DURATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COURSE_DURATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)

    logger.info("Written %d unique courses to %s", len(final), COURSE_DURATIONS_PATH)
    return final


def _print_table(courses: list[dict]) -> None:
    print(f"\n{'Code':<18} {'Sem':<26} {'L':>2} {'P':>2} {'T':>2} {'Hrs':>4}  Course")
    print("-" * 100)
    for c in courses:
        print(
            f"{c['code']:<18} {c['semester']:<26} "
            f"{c['lecture_hrs']:>2} {c['practical_hrs']:>2} {c['tutorial_hrs']:>2} "
            f"{c['total_hours']:>4}  {c['course']}"
        )
    print(f"\nTotal: {len(courses)} unique courses")


if __name__ == "__main__":
    courses = build_registry()
    _print_table(courses)
