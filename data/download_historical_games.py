"""
Download historical college football game data.
"""

import json
import sys
from pathlib import Path

from data.cfbd_api import client


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "raw" / "historical_games"


def download_games(year):
    """Download game data for a completed season."""

    params = {
        "year": year,
        "seasonType": "regular",
    }

    games = client.get(
        "/games",
        params=params,
    )

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIRECTORY / f"{year}.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(games, file, indent=4)

    print(f"Downloaded {len(games)} games for {year}.")
    print(f"Saved to {output_file}")


if __name__ == "__main__":
    year = 2025

    if len(sys.argv) > 1:
        year = int(sys.argv[1])

    download_games(year)
