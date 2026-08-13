"""
Download 2026 college football team statistics from CollegeFootballData.
"""

import json
import os
import sys
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "stats.json"

BASE_URL = "https://api.collegefootballdata.com"


def download_stats(year):
    """Download team season statistics."""

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

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(stats, file, indent=4)

    print(f"Downloaded statistics for {len(stats)} team/stat records.")
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    year = 2026

    if len(sys.argv) > 1:
        year = int(sys.argv[1])

    download_stats(year)
