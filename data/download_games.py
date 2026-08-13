"""
Download college football game data from CollegeFootballData.
"""

import json
import os
import sys
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "games.json"

BASE_URL = "https://api.collegefootballdata.com"


def download_games(year):
    """Download FBS game data for a season."""

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
        f"{BASE_URL}/games",
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    games = response.json()

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
