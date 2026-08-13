"""
Process raw CollegeFootballData game data.

The model focuses on FBS teams while preserving information
about games against lower-division opponents.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "games.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "games.json"


def classify_game(game):
    """Determine the type of game based on team classifications."""

    home_classification = game.get("homeClassification")
    away_classification = game.get("awayClassification")

    if home_classification == "fbs" and away_classification == "fbs":
        return "fbs_vs_fbs"

    if home_classification == "fbs":
        return "fbs_vs_lower"

    if away_classification == "fbs":
        return "fbs_vs_lower"

    return "non_fbs"


def process_game(game):
    """Convert a raw CFBD game into our standardized format."""

    return {
        "game_id": game["id"],
        "season": game["season"],
        "week": game["week"],
        "season_type": game["seasonType"],
        "start_date": game["startDate"],
        "completed": game["completed"],
        "neutral_site": game["neutralSite"],
        "conference_game": game["conferenceGame"],
        "venue_id": game["venueId"],
        "venue": game["venue"],

        "home": {
            "team_id": game["homeId"],
            "team": game["homeTeam"],
            "classification": game["homeClassification"],
            "conference": game["homeConference"],
            "points": game["homePoints"],
        },

        "away": {
            "team_id": game["awayId"],
            "team": game["awayTeam"],
            "classification": game["awayClassification"],
            "conference": game["awayConference"],
            "points": game["awayPoints"],
        },

        "game_classification": classify_game(game),

        "pregame": {
            "home_elo": game["homePregameElo"],
            "away_elo": game["awayPregameElo"],
        },

        "postgame": {
            "home_elo": game["homePostgameElo"],
            "away_elo": game["awayPostgameElo"],
        },
    }


def process_games():
    """Process all raw games."""

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        raw_games = json.load(file)

    processed_games = [
        process_game(game)
        for game in raw_games
    ]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(processed_games, file, indent=4)

    fbs_vs_fbs = sum(
        1
        for game in processed_games
        if game["game_classification"] == "fbs_vs_fbs"
    )

    fbs_vs_lower = sum(
        1
        for game in processed_games
        if game["game_classification"] == "fbs_vs_lower"
    )

    non_fbs = sum(
        1
        for game in processed_games
        if game["game_classification"] == "non_fbs"
    )

    print(f"Raw games: {len(raw_games)}")
    print(f"FBS vs FBS: {fbs_vs_fbs}")
    print(f"FBS vs lower division: {fbs_vs_lower}")
    print(f"Non-FBS: {non_fbs}")
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    process_games()
