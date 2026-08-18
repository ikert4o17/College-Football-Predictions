"""
Download college football team statistics from CollegeFootballData.
"""

import json
import sys
from pathlib import Path

from data.cfbd_api import client


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "stats.json"


def download_stats(year):
    """Download team season statistics."""

    params = {
        "year": year,
        "seasonType": "regular",
    }

    stats = client.get(
        "/stats/season",
        params=params,
    )

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
