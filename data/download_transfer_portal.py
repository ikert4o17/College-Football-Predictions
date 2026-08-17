"""
Download college football transfer portal data.

The portal data will be used to build the 2026 roster/talent
adjustment layer.

For the 2026 preseason model, we are interested in players
entering a new program after the 2025 season.
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
    / "transfer_portal"
)

BASE_URL = "https://api.collegefootballdata.com"


def download_transfer_portal(year):
    """Download transfer portal data for a season."""

    api_key = os.getenv("CFBD_API_KEY")

    if not api_key:
        raise ValueError(
            "CFBD_API_KEY environment variable is not set."
        )

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    params = {
        "year": year,
    }

    response = requests.get(
        f"{BASE_URL}/player/portal",
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    portal_records = response.json()

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
            portal_records,
            file,
            indent=4
        )

    print(
        f"Downloaded "
        f"{len(portal_records)} "
        f"transfer portal records for "
        f"{year}."
    )

    print(
        f"Saved to {output_file}"
    )

    if portal_records:
        print()
        print("First raw CFBD transfer record:")
        print(
            json.dumps(
                portal_records[0],
                indent=4
            )
        )


if __name__ == "__main__":

    year = 2025

    if len(sys.argv) > 1:
        year = int(sys.argv[1])

    download_transfer_portal(year)
