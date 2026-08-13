"""
Download FBS team data from CollegeFootballData.
"""

import json
from pathlib import Path

from data.cfbd_api import CFBDClient


OUTPUT_FILE = Path("data/raw/teams.json")


def download_teams():
    """Download all FBS teams from CFBD."""

    client = CFBDClient()

    teams = client.get("/teams/fbs")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(teams, file, indent=4)

    print(f"Downloaded {len(teams)} teams.")
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    download_teams()
