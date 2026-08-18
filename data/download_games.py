"""
Download college football game data from CollegeFootballData.
"""

import json
import sys
from pathlib import Path

from data.cfbd_api import client


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "games.json"


def download_games(year):
    """Download FBS game data for a season."""

    params = {
        "year": year,
        "seasonType": "regular",
    }

    games = client.get(
        "/games",
        params=params,
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(games, file, indent=4)

    print(f"Downloaded {len(games)} games for {year}.")
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    year = 2026

    if len(sys.argv) > 1:
        year = int(sys.argv[1])

    download_games(year)
