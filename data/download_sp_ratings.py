"""
Download historical SP+ ratings from CFBD.

These ratings will be used as a secondary team-strength baseline
alongside Project Gridiron's own power ratings.

The initial experiment downloads:
    - 2024 SP+
    - 2025 SP+

We will inspect the raw response fields before building the
baseline blending model.

This module does NOT modify the production power-rating system.
"""

import json
import os
import sys
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "sp_ratings"
)

BASE_URL = "https://api.collegefootballdata.com"


def download_sp_ratings(year):
    """Download SP+ ratings for one season."""

    api_key = os.getenv(
        "CFBD_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "CFBD_API_KEY environment variable is not set."
        )

    headers = {
        "Authorization":
            f"Bearer {api_key}"
    }

    params = {
        "year": year,
    }

    response = requests.get(
        f"{BASE_URL}/ratings/sp",
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    records = response.json()

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        OUTPUT_DIRECTORY
        / f"{year}.json"
    )

    with output_file.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            records,
            file,
            indent=4
        )

    print(
        f"Downloaded "
        f"{len(records)} "
        f"SP+ ratings for {year}."
    )

    print(
        f"Saved to {output_file}"
    )

    return records


def download_sp_history(
    start_year,
    end_year
):
    """Download SP+ ratings for a range of seasons."""

    print("=" * 70)

    print(
        "CFBD SP+ RATINGS"
    )

    print("=" * 70)

    print(
        f"Downloading SP+ ratings "
        f"{start_year} through {end_year}."
    )

    print()

    total_records = 0
    first_record = None

    for year in range(
        start_year,
        end_year + 1
    ):

        records = download_sp_ratings(
            year
        )

        total_records += len(
            records
        )

        if (
            first_record is None
            and records
        ):
            first_record = records[0]

    print()

    print(
        f"Total SP+ records downloaded: "
        f"{total_records}"
    )

    if first_record:

        print()

        print(
            "FIRST RAW CFBD SP+ RECORD"
        )

        print("-" * 70)

        print(
            json.dumps(
                first_record,
                indent=4
            )
        )

        print()

        print(
            "FIELDS"
        )

        print("-" * 70)

        for key in sorted(
            first_record.keys()
        ):

            print(
                key
            )


if __name__ == "__main__":

    start_year = 2024
    end_year = 2025

    if len(sys.argv) > 1:
        start_year = int(
            sys.argv[1]
        )

    if len(sys.argv) > 2:
        end_year = int(
            sys.argv[2]
        )

    download_sp_history(
        start_year,
        end_year
    )
