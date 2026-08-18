"""
Download historical college football team statistics.
"""

import json
import sys
from pathlib import Path

from data.cfbd_api import client


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "raw" / "historical_stats"


def download_stats(year):
    """Download team statistics for a completed season."""

    params = {
        "year": year,
        "seasonType": "regular",
    }

    stats = client.get(
        "/stats/season",
        params=params,
    )

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
