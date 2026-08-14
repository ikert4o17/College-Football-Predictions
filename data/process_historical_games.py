"""
Process historical CFBD games into model-ready results.
"""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def classify_game(game):
    """Classify a game based on team divisions."""

    home_classification = game.get("homeClassification")
    away_classification = game.get("awayClassification")

    if (
        home_classification == "fbs"
        and away_classification == "fbs"
    ):
        return "fbs_vs_fbs"

    if (
        home_classification == "fbs"
        or away_classification == "fbs"
    ):
        return "fbs_vs_lower"

    return "non_fbs"


def process_game(game):
    """Convert one raw game into a standardized result."""

    home_points = game.get("homePoints")
    away_points = game.get("awayPoints")

    if home_points is None or away_points is None:
        return None

    home_margin = home_points - away_points
    away_margin = away_points - home_points

    if home_margin > 0:
        winner = "home"
    elif away_margin > 0:
        winner = "away"
    else:
        winner = "tie"

    return {
        "game_id": game["id"],
        "season": game["season"],
        "week": game["week"],
        "season_type": game["seasonType"],
        "start_date": game["startDate"],
        "completed": game["completed"],
        "neutral_site": game["neutralSite"],
        "conference_game": game["conferenceGame"],
        "venue": game.get("venue"),
        "home": {
            "team_id": game["homeId"],
            "team": game["homeTeam"],
            "classification": game["homeClassification"],
            "conference": game["homeConference"],
            "points": home_points,
            "margin": home_margin,
        },
        "away": {
            "team_id": game["awayId"],
            "team": game["awayTeam"],
            "classification": game["awayClassification"],
            "conference": game["awayConference"],
            "points": away_points,
            "margin": away_margin,
        },
        "winner": winner,
        "total_points": home_points + away_points,
        "game_classification": classify_game(game),
    }


def process_games(year):
    """Process historical games for a specific year."""

    input_file = (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "historical_games"
        / f"{year}.json"
    )

    output_file = (
        PROJECT_ROOT
        / "data"
        / "processed"
        / f"historical_games_{year}.json"
    )

    if not input_file.exists():
        raise FileNotFoundError(
            f"Historical games file not found: {input_file}"
        )

    with input_file.open("r", encoding="utf-8") as file:
        raw_games = json.load(file)

    processed_games = []

    for game in raw_games:
        processed = process_game(game)

        if processed is not None:
            processed_games.append(processed)

    processed_games = [
        game
        for game in processed_games
        if game["game_classification"] != "non_fbs"
    ]

    processed_games.sort(
        key=lambda game: (
            game["week"],
            game["start_date"]
        )
    )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(
            processed_games,
            file,
            indent=4
        )

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

    print(f"Processed games: {len(processed_games)}")
    print(f"FBS vs FBS: {fbs_vs_fbs}")
    print(f"FBS vs lower: {fbs_vs_lower}")
    print(f"Saved to {output_file}")


if __name__ == "__main__":
    year = 2025

    if len(sys.argv) > 1:
        year = int(sys.argv[1])

    process_games(year)
