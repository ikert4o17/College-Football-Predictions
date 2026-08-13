"""
Download historical college football game data.
"""

import json
import os
import sys
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "raw" / "historical_games"

BASE_URL = "https://api.collegefootballdata.com"


def download_games(year):
    """Download game data for a completed season."""

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

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = OUTPUT_DIRECTORY / f"{year}.json"

    with output_file.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            games,
            file,
            indent=4
        )

    print(
        f"Downloaded {len(games)} games for {year}."
    )

    print(
        f"Saved to {output_file}"
    )


if __name__ == "__main__":
    year = 2025

    if len(sys.argv) > 1:
        year = int(sys.argv[1])

    download_games(year)
