"""
Project Gridiron
CFBD Access Audit

Scans repository Python code for direct CollegeFootballData access that
bypasses data.cfbd_api.client.

Usage:
    python -m data.audit_cfbd_access

Exit codes:
    0 = no suspicious direct CFBD access found
    1 = one or more files require review
"""

from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCAN_DIRECTORIES = [
    PROJECT_ROOT / "data",
    PROJECT_ROOT / "ratings",
    PROJECT_ROOT / "predictions",
]

ALLOWED_FILES = {
    PROJECT_ROOT / "data" / "cfbd_api.py",
    PROJECT_ROOT / "data" / "check_cfbd_usage.py",
    PROJECT_ROOT / "data" / "check_cfbd_quota_guard.py",
    PROJECT_ROOT / "data" / "plan_cfbd_requests.py",
    PROJECT_ROOT / "data" / "audit_cfbd_access.py",
}

IGNORED_DIRECTORY_NAMES = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
}

# Generic HTTP patterns are only suspicious when the file also contains
# CFBD-specific context. This avoids false positives for legitimate external
# sources such as Punt & Rally.
HTTP_PATTERNS = [
    ("requests.get", re.compile(r"\brequests\s*\.\s*get\s*\(")),
    ("requests.post", re.compile(r"\brequests\s*\.\s*post\s*\(")),
    ("requests.request", re.compile(r"\brequests\s*\.\s*request\s*\(")),
    ("requests.Session", re.compile(r"\brequests\s*\.\s*Session\s*\(")),
    (
        "session.get",
        re.compile(r"\b(?:session|self\.session)\s*\.\s*get\s*\("),
    ),
    ("HTTPAdapter retry client", re.compile(r"\bHTTPAdapter\s*\(")),
]

CFBD_SPECIFIC_PATTERNS = [
    (
        "direct CFBD hostname",
        re.compile(r"(?:api\.)?collegefootballdata\.com", re.IGNORECASE),
    ),
    ("locally defined api_get", re.compile(r"^\s*def\s+api_get\s*\(", re.MULTILINE)),
    (
        "locally defined get_json",
        re.compile(r"^\s*def\s+(?:cfbd_)?get_json\s*\(", re.MULTILINE),
    ),
]

CFBD_CONTEXT_PATTERNS = [
    re.compile(r"(?:api\.)?collegefootballdata\.com", re.IGNORECASE),
    re.compile(r"\bCFBD_API_KEY\b"),
    re.compile(r"\bCollegeFootballData\b", re.IGNORECASE),
    re.compile(r"\bCFBD\b", re.IGNORECASE),
]

SHARED_CLIENT_IMPORT_PATTERNS = [
    re.compile(r"from\s+data\.cfbd_api\s+import\s+client"),
    re.compile(r"from\s+data\.cfbd_api\s+import\s+CFBDClient"),
    re.compile(r"import\s+data\.cfbd_api"),
]


def should_ignore(path):
    """Return whether path should be skipped."""

    return any(part in IGNORED_DIRECTORY_NAMES for part in path.parts)


def python_files():
    """Yield Python files in scan directories."""

    for directory in SCAN_DIRECTORIES:
        if not directory.exists():
            continue

        for path in directory.rglob("*.py"):
            if not should_ignore(path):
                yield path


def read_text(path):
    """Read file text safely."""

    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def line_number_for_offset(text, offset):
    """Return 1-based line number."""

    return text.count("\n", 0, offset) + 1


def has_shared_client_import(text):
    """Return whether file imports the shared CFBD client."""

    return any(pattern.search(text) for pattern in SHARED_CLIENT_IMPORT_PATTERNS)


def has_cfbd_context(text):
    """Return whether file contains CFBD-specific context."""

    return any(pattern.search(text) for pattern in CFBD_CONTEXT_PATTERNS)


def relative_path(path):
    """Return repository-relative path."""

    try:
        return path.relative_to(PROJECT_ROOT)
    except ValueError:
        return path


def collect_matches(text):
    """Collect suspicious patterns from one file."""

    matches = []

    patterns = list(CFBD_SPECIFIC_PATTERNS)

    if has_cfbd_context(text):
        patterns.extend(HTTP_PATTERNS)

    for label, pattern in patterns:
        for match in pattern.finditer(text):
            matches.append(
                {
                    "type": label,
                    "line": line_number_for_offset(text, match.start()),
                    "match": match.group(0).strip(),
                }
            )

    return sorted(matches, key=lambda item: (item["line"], item["type"]))


def audit_file(path):
    """Audit one Python file."""

    if path in ALLOWED_FILES:
        return None

    text = read_text(path)

    if text is None:
        return None

    matches = collect_matches(text)

    if not matches:
        return None

    return {
        "path": path,
        "relative_path": relative_path(path),
        "uses_shared_client": has_shared_client_import(text),
        "matches": matches,
    }


def run_audit():
    """Run repository CFBD access audit."""

    findings = []
    scanned = 0

    for path in python_files():
        scanned += 1
        result = audit_file(path)
        if result:
            findings.append(result)

    findings.sort(key=lambda item: str(item["relative_path"]))

    print("=" * 78)
    print("PROJECT GRIDIRON CFBD ACCESS AUDIT")
    print("=" * 78)
    print()
    print(f"Python files scanned: {scanned}")
    print(f"Files requiring review: {len(findings)}")
    print()

    if not findings:
        print("PASS")
        print()
        print(
            "No suspicious direct CFBD access patterns were found "
            "outside approved infrastructure files."
        )
        return 0

    print("FILES REQUIRING REVIEW")
    print("-" * 78)
    print()

    for finding in findings:
        print(finding["relative_path"])
        print(f"  imports shared client: {finding['uses_shared_client']}")

        for item in finding["matches"]:
            print(f"  line {item['line']}: {item['type']}")
            print(f"    {item['match']}")

        print()

    print("=" * 78)
    print("AUDIT RESULT: REVIEW REQUIRED")
    print("=" * 78)
    print()
    print("Any real CFBD request outside data.cfbd_api can bypass:")
    print("  - persistent cache")
    print("  - cache freshness policy")
    print("  - monthly quota guard")
    print("  - per-run request budget")
    print("  - centralized retry handling")
    print()
    print("Files listed above should be migrated to:")
    print()
    print("    from data.cfbd_api import client")
    print()
    print("    data = client.get(endpoint, params)")

    return 1


if __name__ == "__main__":
    sys.exit(run_audit())
