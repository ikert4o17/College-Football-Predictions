"""
Process raw CFBD team data into the model's standardized team format.
"""

import json
import sys
from pathlib import Path

# Add the repository root to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.team_data import create_team


INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "teams.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "teams.json"


def process_team(team):
    """Convert one CFBD team into our standardized format."""

    location = team.get("location") or {}

    return create_team(
        team_id=team["id"],
        name=team["school"],
        abbreviation=team["abbreviation"],
        conference=team.get("conference"),
        mascot=team.get("mascot"),
        stadium=location.get("name"),
        city=location.get("city"),
        state=location.get("state"),
        timezone=location.get("timezone"),
        elevation=location.get("elevation"),
        capacity=location.get("capacity"),
        grass=location.get("grass"),
        dome=location.get("dome"),
    )


def process_teams():
    """Process all raw CFBD teams."""

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        raw_teams = json.load(file)

    processed_teams = [
        process_team(team)
        for team in raw_teams
    ]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(processed_teams, file, indent=4)

    print(f"Processed {len(processed_teams)} teams.")
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    process_teams()
