"""
Project Gridiron
Returning Production Downloader

Downloads CFBD returning-production data through the shared Project
Gridiron client.

Usage:
    python -m data.download_returning_production 2025
    python -m data.download_returning_production 2026

Output:
    data/raw/returning_production/<year>.json

Behavior:
    1. Reuse an existing valid downloaded file by default.
    2. Set FORCE_CFBD_REFRESH=1 to force a fresh API request.
    3. Delegate CFBD cache policy, quota protection, request budgeting,
       retries, and Retry-After handling to data.cfbd_api.client.
"""

import json
import os
import sys
from pathlib import Path

from data.cfbd_api import client


PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "returning_production"
)

ENDPOINT = "/player/returning"


def force_refresh_enabled():
    """Return whether user requested a forced API refresh."""

    value = os.getenv("FORCE_CFBD_REFRESH", "").strip().lower()

    return value in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def output_file(year):
    """Return raw output path."""

    return OUTPUT_DIRECTORY / f"{year}.json"


def load_json(path):
    """Load JSON."""

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data, path):
    """Save JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def existing_file_is_valid(path):
    """Check whether an existing returning-production file is usable."""

    if not path.exists():
        return False

    try:
        data = load_json(path)
    except (OSError, json.JSONDecodeError):
        return False

    return isinstance(data, list) and len(data) > 0


def download_returning_production(year):
    """Download returning production for one season."""

    destination = output_file(year)

    print("=" * 76)
    print(f"CFBD RETURNING PRODUCTION - {year}")
    print("=" * 76)

    if existing_file_is_valid(destination) and not force_refresh_enabled():
        data = load_json(destination)

        print()
        print("Existing valid file found.")
        print("Skipping CFBD API request.")
        print()
        print(f"Records: {len(data)}")
        print("Using cached file:")
        print(destination)
        print()
        print("Set FORCE_CFBD_REFRESH=1 to force a new download.")

        return data

    data = client.get(
        ENDPOINT,
        params={"year": year},
    )

    if not isinstance(data, list):
        raise ValueError(
            "Expected CFBD returning-production response to be a list."
        )

    save_json(data, destination)

    print()
    print("RETURNING PRODUCTION DOWNLOAD COMPLETE")
    print("-" * 76)
    print(f"Season: {year}")
    print(f"Records downloaded: {len(data)}")
    print("Saved to:")
    print(destination)

    if data:
        print()
        print("FIRST RECORD")
        print("-" * 76)
        print(json.dumps(data[0], indent=4))

    return data


if __name__ == "__main__":
    year = 2025

    if len(sys.argv) > 1:
        year = int(sys.argv[1])

    download_returning_production(year)
