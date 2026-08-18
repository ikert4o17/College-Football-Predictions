"""
Project Gridiron
CFBD Access Audit

Purpose
-------
Scan the repository for code paths that may access CollegeFootballData
directly instead of using the shared Project Gridiron client:

    data.cfbd_api.client

The goal is to ensure all CFBD traffic flows through one path:

    downloader
        ->
    data.cfbd_api.client
        ->
    cache policy
        ->
    cache lookup
        ->
    monthly quota guard
        ->
    per-run request budget
        ->
    CFBD

This audit is intentionally conservative. It may flag some harmless
patterns for manual review.

Usage:
    python -m data.audit_cfbd_access

Exit codes:
    0 = no suspicious direct-access patterns found
    1 = one or more files require review
"""

from pathlib import Path
import re
import sys


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)


# ============================================================
# PATH FILTERS
# ============================================================

SCAN_DIRECTORIES = [
    PROJECT_ROOT / "data",
    PROJECT_ROOT / "ratings",
    PROJECT_ROOT / "predictions",
]

ALLOWED_FILES = {
    # Shared client is expected to contain requests/session logic.
    PROJECT_ROOT / "data" / "cfbd_api.py",

    # Usage / quota diagnostics intentionally call /info directly.
    PROJECT_ROOT / "data" / "check_cfbd_usage.py",
    PROJECT_ROOT / "data" / "check_cfbd_quota_guard.py",

    # Dry-run planner may call /info directly.
    PROJECT_ROOT / "data" / "plan_cfbd_requests.py",

    # This audit file itself contains search patterns.
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


# ============================================================
# SUSPICIOUS PATTERNS
# ============================================================

PATTERNS = [
    (
        "requests.get",
        re.compile(
            r"\brequests\s*\.\s*get\s*\("
        ),
    ),
    (
        "requests.post",
        re.compile(
            r"\brequests\s*\.\s*post\s*\("
        ),
    ),
    (
        "requests.request",
        re.compile(
            r"\brequests\s*\.\s*request\s*\("
        ),
    ),
    (
        "requests.Session",
        re.compile(
            r"\brequests\s*\.\s*Session\s*\("
        ),
    ),
    (
        "session.get",
        re.compile(
            r"\b(?:session|self\.session)\s*\.\s*get\s*\("
        ),
    ),
    (
        "direct CFBD hostname",
        re.compile(
            r"(?:api\.)?collegefootballdata\.com",
            re.IGNORECASE,
        ),
    ),
    (
        "locally defined api_get",
        re.compile(
            r"^\s*def\s+api_get\s*\(",
            re.MULTILINE,
        ),
    ),
    (
        "locally defined get_json",
        re.compile(
            r"^\s*def\s+(?:cfbd_)?get_json\s*\(",
            re.MULTILINE,
        ),
    ),
    (
        "HTTPAdapter retry client",
        re.compile(
            r"\bHTTPAdapter\s*\("
        ),
    ),
]


# ============================================================
# SHARED CLIENT PATTERNS
# ============================================================

SHARED_CLIENT_IMPORT_PATTERNS = [
    re.compile(
        r"from\s+data\.cfbd_api\s+import\s+client"
    ),
    re.compile(
        r"from\s+data\.cfbd_api\s+import\s+CFBDClient"
    ),
    re.compile(
        r"import\s+data\.cfbd_api"
    ),
]


# ============================================================
# HELPERS
# ============================================================

def should_ignore(path):
    """Return whether path should be skipped."""

    for part in path.parts:

        if part in IGNORED_DIRECTORY_NAMES:
            return True

    return False


def python_files():
    """Yield Python files in scan directories."""

    for directory in SCAN_DIRECTORIES:

        if not directory.exists():
            continue

        for path in directory.rglob("*.py"):

            if should_ignore(
                path
            ):
                continue

            yield path


def read_text(path):
    """Read file text safely."""

    try:

        return path.read_text(
            encoding="utf-8"
        )

    except (
        OSError,
        UnicodeDecodeError
    ):

        return None


def line_number_for_offset(
    text,
    offset
):
    """Return 1-based line number."""

    return (
        text.count(
            "\n",
            0,
            offset,
        )
        +
        1
    )


def has_shared_client_import(text):
    """Return whether file imports shared CFBD client."""

    for pattern in SHARED_CLIENT_IMPORT_PATTERNS:

        if pattern.search(
            text
        ):

            return True

    return False


def relative_path(path):
    """Return repository-relative path."""

    try:

        return path.relative_to(
            PROJECT_ROOT
        )

    except ValueError:

        return path


# ============================================================
# AUDIT
# ============================================================

def audit_file(path):
    """Audit one Python file."""

    if path in ALLOWED_FILES:
        return None

    text = read_text(
        path
    )

    if text is None:
        return None

    matches = []

    for (
        label,
        pattern,
    ) in PATTERNS:

        for match in pattern.finditer(
            text
        ):

            matches.append(
                {
                    "type":
                        label,

                    "line":
                        line_number_for_offset(
                            text,
                            match.start(),
                        ),

                    "match":
                        match.group(
                            0
                        ).strip(),
                }
            )

    if not matches:
        return None

    return {
        "path":
            path,

        "relative_path":
            relative_path(
                path
            ),

        "uses_shared_client":
            has_shared_client_import(
                text
            ),

        "matches":
            sorted(
                matches,
                key=lambda item:
                    (
                        item[
                            "line"
                        ],
                        item[
                            "type"
                        ],
                    ),
            ),
    }


def run_audit():
    """Run repository CFBD access audit."""

    findings = []

    scanned = 0

    for path in python_files():

        scanned += 1

        result = audit_file(
            path
        )

        if result:

            findings.append(
                result
            )

    findings.sort(
        key=lambda item:
            str(
                item[
                    "relative_path"
                ]
            )
    )

    print("=" * 78)

    print(
        "PROJECT GRIDIRON CFBD ACCESS AUDIT"
    )

    print("=" * 78)

    print()

    print(
        f"Python files scanned: "
        f"{scanned}"
    )

    print(
        f"Files requiring review: "
        f"{len(findings)}"
    )

    print()

    if not findings:

        print(
            "PASS"
        )

        print()

        print(
            "No suspicious direct CFBD access patterns were found "
            "outside approved infrastructure files."
        )

        return 0

    print(
        "FILES REQUIRING REVIEW"
    )

    print("-" * 78)

    print()

    for finding in findings:

        print(
            finding[
                "relative_path"
            ]
        )

        print(
            f"  imports shared client: "
            f"{finding['uses_shared_client']}"
        )

        for item in finding[
            "matches"
        ]:

            print(
                f"  line "
                f"{item['line']}: "
                f"{item['type']}"
            )

            print(
                f"    {item['match']}"
            )

        print()

    print("=" * 78)

    print(
        "AUDIT RESULT: REVIEW REQUIRED"
    )

    print("=" * 78)

    print()

    print(
        "Any real CFBD request outside data.cfbd_api can bypass:"
    )

    print(
        "  - persistent cache"
    )

    print(
        "  - cache freshness policy"
    )

    print(
        "  - per-run request budget"
    )

    print(
        "  - centralized retry handling"
    )

    print()

    print(
        "Files listed above should be reviewed and migrated to:"
    )

    print()

    print(
        "    from data.cfbd_api import client"
    )

    print()

    print(
        "    data = client.get(endpoint, params)"
    )

    return 1


if __name__ == "__main__":

    sys.exit(
        run_audit()
    )
