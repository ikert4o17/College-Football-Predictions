"""
Download historical college football team statistics.
"""

import json
import os
import sys
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "raw" / "historical_stats"

BASE_URL = "https://api.collegefootballdata.com"


def download_stats(year):
    """Download team statistics for a completed season."""

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
        "seasonType": "regular",
    }

    response = requests.get(
        f"{BASE_URL}/stats/season",
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    stats = response.json()

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIRECTORY / f"{year}.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(stats, file, indent=4)

    print(f"Downloaded {len(stats)} stat records for {year}.")
    print(f"Saved to {output_file}")


if __name__ == "__main__":
    year = 2025

    if len(sys.argv) > 1:
        year = int(sys.argv[1])

    download_stats(year)
