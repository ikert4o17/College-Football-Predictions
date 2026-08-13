"""
Baseline backtester for the 2025 FBS power ratings.

IMPORTANT:
This first version uses full-season 2025 power ratings.
It is a validation baseline, not a true predictive backtest.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

GAMES_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "historical_games_2025.json"
)

RATINGS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "power_ratings_2025.json"
)


def load_json(path):
    """Load a JSON file."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def build_rating_lookup(ratings):
    """Create a team-to-rating lookup."""

    return {
        team["team"]: team
        for team in ratings
    }


def predict_winner(
    away_team,
    home_team,
    ratings
):
    """Predict the winner using power ratings."""

    away = ratings.get(away_team)
    home = ratings.get(home_team)

    if away is None or home is None:
        return None

    if home["power_rating"] >= away["power_rating"]:
        return home_team

    return away_team


def backtest():
    """Run the baseline backtest."""

    games = load_json(GAMES_FILE)
    ratings = load_json(RATINGS_FILE)

    rating_lookup = build_rating_lookup(
        ratings
    )

    total_games = 0
    correct_predictions = 0
    skipped_games = 0

    for game in games:

        if game.get(
            "game_classification"
        ) != "fbs_vs_fbs":
            continue

        away_team = game.get(
            "awayTeam"
        )

        home_team = game.get(
            "homeTeam"
        )

        away_points = game.get(
            "awayPoints"
        )

        home_points = game.get(
            "homePoints"
        )

        if (
            away_team is None
            or home_team is None
            or away_points is None
            or home_points is None
        ):
            skipped_games += 1
            continue

        predicted_winner = predict_winner(
            away_team,
            home_team,
            rating_lookup
        )

        if predicted_winner is None:
            skipped_games += 1
            continue

        if away_points > home_points:
            actual_winner = away_team
        elif home_points > away_points:
            actual_winner = home_team
        else:
            skipped_games += 1
            continue

        total_games += 1

        if predicted_winner == actual_winner:
            correct_predictions += 1

    if total_games == 0:
        print("No games available for backtesting.")
        return

    accuracy = (
        correct_predictions
        / total_games
    )

    print()
    print("=" * 50)
    print("2025 FBS POWER RATING BASELINE BACKTEST")
    print("=" * 50)
    print()
    print(
        f"Games tested: {total_games}"
    )
    print(
        f"Correct predictions: "
        f"{correct_predictions}"
    )
    print(
        f"Incorrect predictions: "
        f"{total_games - correct_predictions}"
    )
    print(
        f"Skipped games: {skipped_games}"
    )
    print(
        f"Prediction accuracy: "
        f"{accuracy:.3%}"
    )
    print()
    print(
        "WARNING: These ratings use "
        "full-season 2025 data."
    )
    print(
        "This is a baseline validation, "
        "not a true predictive backtest."
    )
    print("=" * 50)


if __name__ == "__main__":
    backtest()
