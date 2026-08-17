"""
Download NFL Draft picks from CFBD.

This data will be used to identify meaningful roster losses
from college teams entering the following season.

For example:
    2025 NFL Draft picks represent players lost after the 2024 season.

This module does NOT modify the power-rating system.
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
    / "draft_picks"
)

BASE_URL = "https://api.collegefootballdata.com"


def download_draft_picks(year):
    """Download NFL Draft picks for one draft year."""

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
        f"{BASE_URL}/draft/picks",
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

    print("=" * 60)

    print(
        f"{year} NFL DRAFT PICKS"
    )

    print("=" * 60)

    print(
        f"Draft records downloaded: "
        f"{len(records)}"
    )

    print(
        f"Saved to {output_file}"
    )

    if records:

        print()

        print(
            "FIRST RAW CFBD DRAFT RECORD"
        )

        print("-" * 60)

        print(
            json.dumps(
                records[0],
                indent=4
            )
        )

        print()

        print(
            "FIELDS"
        )

        print("-" * 60)

        for key in sorted(
            records[0].keys()
        ):

            print(
                key
            )


if __name__ == "__main__":

    year = 2025

    if len(sys.argv) > 1:

        year = int(
            sys.argv[1]
        )

    download_draft_picks(
        year
    )
