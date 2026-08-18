"""
Project Gridiron
CFBD Cache Manifest Builder

Purpose
-------
Create a human-readable index of persisted CFBD cache entries.

The CFBD request cache uses hashed filenames, which is efficient for
lookup but difficult to inspect manually. This script scans all cached
JSON responses and produces a manifest containing:

    - endpoint
    - request parameters
    - season/year where available
    - saved timestamp
    - cache filename
    - record count / response type

Usage:
    python -m data.build_cfbd_cache_manifest

Input:
    data/cache/cfbd/*.json

Output:
    data/cache/cfbd/manifest.json

The request-budget state file is ignored.
"""

import json
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

CACHE_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "cache"
    / "cfbd"
)

MANIFEST_FILE = (
    CACHE_DIRECTORY
    / "manifest.json"
)

REQUEST_BUDGET_STATE_FILE = (
    CACHE_DIRECTORY
    / "request_budget_state.json"
)


def load_json(path):
    """Load JSON safely."""

    try:
        with path.open(
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(
                file
            )

    except (
        OSError,
        json.JSONDecodeError
    ):

        return None


def response_summary(data):
    """Build compact metadata about cached response."""

    if isinstance(
        data,
        list
    ):

        return {
            "response_type":
                "list",

            "record_count":
                len(data),
        }

    if isinstance(
        data,
        dict
    ):

        return {
            "response_type":
                "dict",

            "record_count":
                len(data),
        }

    return {
        "response_type":
            type(data).__name__,

        "record_count":
            None,
    }


def extract_year(params):
    """Extract year/season from request parameters."""

    if not isinstance(
        params,
        dict
    ):

        return None

    for key in (
        "year",
        "season",
    ):

        value = params.get(
            key
        )

        if value is not None:

            return value

    return None


def build_manifest():
    """Scan CFBD cache and generate manifest."""

    CACHE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    entries = []

    skipped = []

    for path in sorted(
        CACHE_DIRECTORY.glob(
            "*.json"
        )
    ):

        if path == MANIFEST_FILE:
            continue

        if path == REQUEST_BUDGET_STATE_FILE:
            continue

        payload = load_json(
            path
        )

        if not isinstance(
            payload,
            dict
        ):

            skipped.append(
                {
                    "file":
                        path.name,

                    "reason":
                        "invalid_or_non_dict_payload",
                }
            )

            continue

        if (
            "endpoint" not in payload
            or
            "data" not in payload
        ):

            skipped.append(
                {
                    "file":
                        path.name,

                    "reason":
                        "not_cfbd_cache_entry",
                }
            )

            continue

        endpoint = payload.get(
            "endpoint"
        )

        params = (
            payload.get(
                "params"
            )
            or {}
        )

        data = payload.get(
            "data"
        )

        summary = response_summary(
            data
        )

        entries.append(
            {
                "endpoint":
                    endpoint,

                "params":
                    params,

                "year":
                    extract_year(
                        params
                    ),

                "saved_at_utc":
                    payload.get(
                        "saved_at_utc"
                    ),

                "cache_file":
                    path.name,

                "response_type":
                    summary[
                        "response_type"
                    ],

                "record_count":
                    summary[
                        "record_count"
                    ],
            }
        )

    entries.sort(
        key=lambda entry:
            (
                str(
                    entry.get(
                        "endpoint"
                    )
                ),
                str(
                    entry.get(
                        "year"
                    )
                ),
                json.dumps(
                    entry.get(
                        "params"
                    ),
                    sort_keys=True,
                    default=str,
                ),
            )
    )

    manifest = {
        "cache_directory":
            str(
                CACHE_DIRECTORY
            ),

        "entry_count":
            len(
                entries
            ),

        "skipped_file_count":
            len(
                skipped
            ),

        "entries":
            entries,

        "skipped_files":
            skipped,
    }

    with MANIFEST_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            manifest,
            file,
            indent=2,
        )

    print("=" * 78)

    print(
        "PROJECT GRIDIRON CFBD CACHE MANIFEST"
    )

    print("=" * 78)

    print()

    print(
        f"Cache entries: "
        f"{len(entries)}"
    )

    print(
        f"Skipped files: "
        f"{len(skipped)}"
    )

    print()

    if not entries:

        print(
            "No persisted CFBD cache entries were found."
        )

    else:

        print(
            "CACHED REQUESTS"
        )

        print("-" * 78)

        for entry in entries:

            endpoint = entry.get(
                "endpoint"
            )

            params = entry.get(
                "params"
            )

            record_count = entry.get(
                "record_count"
            )

            saved_at = entry.get(
                "saved_at_utc"
            )

            print(
                f"{endpoint}"
            )

            print(
                f"  params: "
                f"{params}"
            )

            print(
                f"  records: "
                f"{record_count}"
            )

            print(
                f"  saved: "
                f"{saved_at}"
            )

            print(
                f"  file: "
                f"{entry['cache_file']}"
            )

            print()

    if skipped:

        print(
            "SKIPPED FILES"
        )

        print("-" * 78)

        for item in skipped:

            print(
                f"{item['file']}: "
                f"{item['reason']}"
            )

        print()

    print(
        f"Manifest saved to:"
    )

    print(
        MANIFEST_FILE
    )

    return manifest


if __name__ == "__main__":

    build_manifest()
