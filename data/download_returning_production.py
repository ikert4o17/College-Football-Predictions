"""
Project Gridiron
Returning Production Downloader

Downloads CFBD returning-production data for a requested season.

Usage:
    python -m data.download_returning_production 2025
    python -m data.download_returning_production 2026

Output:
    data/raw/returning_production/<year>.json

Behavior:
    1. Reuse an existing valid downloaded file by default.
    2. Set FORCE_CFBD_REFRESH=1 to force a fresh API request.
    3. Retry temporary HTTP 429 responses with backoff.
    4. Respect Retry-After when CFBD supplies it.
    5. Fail with a clear message if repeated 429 responses continue.

This helps avoid burning CFBD API calls on historical data that has
already been downloaded successfully.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent

BASE_URL = "https://api.collegefootballdata.com"

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "returning_production"
)

ENDPOINT = "/player/returning"


# ============================================================
# RETRY SETTINGS
# ============================================================

MAX_ATTEMPTS = 5

DEFAULT_BACKOFF_SECONDS = [
    10,
    20,
    40,
    60,
]


# ============================================================
# GENERAL HELPERS
# ============================================================

def get_api_key():
    """Return CFBD API key."""

    api_key = os.getenv(
        "CFBD_API_KEY"
    )

    if not api_key:

        raise ValueError(
            "CFBD_API_KEY environment variable is not set."
        )

    return api_key


def force_refresh_enabled():
    """Return whether user requested a forced API refresh."""

    value = (
        os.getenv(
            "FORCE_CFBD_REFRESH",
            ""
        )
        .strip()
        .lower()
    )

    return value in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def output_file(year):
    """Return raw output path."""

    return (
        OUTPUT_DIRECTORY
        / f"{year}.json"
    )


def load_json(path):
    """Load JSON."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(
            file
        )


def save_json(
    data,
    path
):
    """Save JSON."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4
        )


def existing_file_is_valid(path):
    """
    Check whether an existing returning-production file is usable.
    """

    if not path.exists():
        return False

    try:

        data = load_json(
            path
        )

    except (
        OSError,
        json.JSONDecodeError
    ):

        return False

    return (
        isinstance(
            data,
            list
        )
        and
        len(data) > 0
    )


# ============================================================
# HTTP HELPERS
# ============================================================

def print_error_response(response):
    """Print useful CFBD error information."""

    print()

    print(
        "CFBD ERROR RESPONSE"
    )

    print("-" * 76)

    try:

        payload = response.json()

        print(
            json.dumps(
                payload,
                indent=4
            )
        )

    except ValueError:

        text = (
            response.text
            or ""
        )

        print(
            text[:3000]
        )


def retry_after_seconds(response):
    """
    Parse HTTP Retry-After.

    Retry-After can be:
        number of seconds
        HTTP date
    """

    value = response.headers.get(
        "Retry-After"
    )

    if not value:
        return None

    value = value.strip()

    # --------------------------------------------------------
    # Integer seconds
    # --------------------------------------------------------

    try:

        seconds = int(
            value
        )

        return max(
            seconds,
            0
        )

    except ValueError:
        pass

    # --------------------------------------------------------
    # HTTP date
    # --------------------------------------------------------

    try:

        retry_time = parsedate_to_datetime(
            value
        )

        if retry_time.tzinfo is None:

            retry_time = retry_time.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(
            timezone.utc
        )

        seconds = int(
            (
                retry_time
                -
                now
            ).total_seconds()
        )

        return max(
            seconds,
            0
        )

    except (
        TypeError,
        ValueError,
        OverflowError
    ):

        return None


def backoff_seconds(
    attempt,
    response
):
    """Determine retry delay."""

    header_delay = retry_after_seconds(
        response
    )

    if header_delay is not None:

        return min(
            header_delay,
            120
        )

    index = min(
        attempt - 1,
        len(
            DEFAULT_BACKOFF_SECONDS
        ) - 1
    )

    return DEFAULT_BACKOFF_SECONDS[
        index
    ]


def api_get_with_retry(
    endpoint,
    params
):
    """Run CFBD GET request with safe 429 handling."""

    headers = {
        "Authorization":
            f"Bearer {get_api_key()}"
    }

    url = (
        f"{BASE_URL}"
        f"{endpoint}"
    )

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1
    ):

        print()

        print(
            f"GET {endpoint}"
        )

        print(
            f"Parameters: {params}"
        )

        print(
            f"Attempt: "
            f"{attempt}/{MAX_ATTEMPTS}"
        )

        try:

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=60,
            )

        except requests.RequestException as error:

            if attempt >= MAX_ATTEMPTS:

                raise RuntimeError(
                    "CFBD request failed after repeated "
                    "network errors."
                ) from error

            delay = DEFAULT_BACKOFF_SECONDS[
                min(
                    attempt - 1,
                    len(
                        DEFAULT_BACKOFF_SECONDS
                    ) - 1
                )
            ]

            print(
                f"Network error: {error}"
            )

            print(
                f"Retrying after "
                f"{delay} seconds."
            )

            time.sleep(
                delay
            )

            continue

        print(
            f"Status code: "
            f"{response.status_code}"
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if response.status_code == 200:

            try:

                data = response.json()

            except ValueError as error:

                raise ValueError(
                    "CFBD returned invalid JSON."
                ) from error

            if not isinstance(
                data,
                list
            ):

                raise ValueError(
                    "Expected CFBD returning-production "
                    "response to be a list."
                )

            return data

        # ----------------------------------------------------
        # RATE LIMIT
        # ----------------------------------------------------

        if response.status_code == 429:

            print_error_response(
                response
            )

            if attempt >= MAX_ATTEMPTS:

                raise RuntimeError(
                    "CFBD returned HTTP 429 Too Many Requests "
                    "on every attempt. This may be temporary "
                    "rate limiting or the API key may have "
                    "reached its usage quota. The downloader "
                    "will not continue retrying."
                )

            delay = backoff_seconds(
                attempt,
                response
            )

            print()

            print(
                "CFBD rate limit encountered."
            )

            print(
                f"Retrying after "
                f"{delay} seconds."
            )

            time.sleep(
                delay
            )

            continue

        # ----------------------------------------------------
        # SERVER ERRORS
        # ----------------------------------------------------

        if (
            response.status_code
            >= 500
        ):

            print_error_response(
                response
            )

            if attempt >= MAX_ATTEMPTS:

                response.raise_for_status()

            delay = DEFAULT_BACKOFF_SECONDS[
                min(
                    attempt - 1,
                    len(
                        DEFAULT_BACKOFF_SECONDS
                    ) - 1
                )
            ]

            print()

            print(
                f"CFBD server error. "
                f"Retrying after {delay} seconds."
            )

            time.sleep(
                delay
            )

            continue

        # ----------------------------------------------------
        # NON-RETRYABLE ERROR
        # ----------------------------------------------------

        print_error_response(
            response
        )

        response.raise_for_status()

    raise RuntimeError(
        "CFBD request ended unexpectedly."
    )


# ============================================================
# DOWNLOAD
# ============================================================

def download_returning_production(year):
    """Download returning production for one season."""

    destination = output_file(
        year
    )

    print("=" * 76)

    print(
        f"CFBD RETURNING PRODUCTION - {year}"
    )

    print("=" * 76)

    # --------------------------------------------------------
    # CACHE
    # --------------------------------------------------------

    if (
        existing_file_is_valid(
            destination
        )
        and
        not force_refresh_enabled()
    ):

        data = load_json(
            destination
        )

        print()

        print(
            "Existing valid file found."
        )

        print(
            "Skipping CFBD API request."
        )

        print()

        print(
            f"Records: "
            f"{len(data)}"
        )

        print(
            f"Using cached file:"
        )

        print(
            destination
        )

        print()

        print(
            "Set FORCE_CFBD_REFRESH=1 "
            "to force a new download."
        )

        return data

    # --------------------------------------------------------
    # API DOWNLOAD
    # --------------------------------------------------------

    data = api_get_with_retry(
        ENDPOINT,
        {
            "year":
                year,
        }
    )

    save_json(
        data,
        destination
    )

    print()

    print(
        "RETURNING PRODUCTION DOWNLOAD COMPLETE"
    )

    print("-" * 76)

    print(
        f"Season: "
        f"{year}"
    )

    print(
        f"Records downloaded: "
        f"{len(data)}"
    )

    print(
        f"Saved to:"
    )

    print(
        destination
    )

    if data:

        print()

        print(
            "FIRST RECORD"
        )

        print("-" * 76)

        print(
            json.dumps(
                data[0],
                indent=4
            )
        )

    return data


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    year = 2025

    if len(
        sys.argv
    ) > 1:

        year = int(
            sys.argv[1]
        )

    download_returning_production(
        year
    )
