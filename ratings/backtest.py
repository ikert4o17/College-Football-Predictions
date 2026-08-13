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


def is_fbs_vs_fbs(game):
    """Check whether the game is FBS vs FBS."""

    return (
        game.get("game_classification")
        == "fbs_vs_fbs"
    )


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
    fbs_games_found = 0

    missing_ratings = []

    print()
    print(
        f"Loaded {len(games)} historical games."
    )

    print(
        f"Loaded {len(ratings)} power ratings."
    )

    for game in games:

        if not is_fbs_vs_fbs(game):
            continue

        fbs_games_found += 1

        home = game.get("home")
        away = game.get("away")

        if home is None or away is None:
            skipped_games += 1
            continue

        home_team = home.get("team")
        away_team = away.get("team")

        home_points = home.get("points")
        away_points = away.get("points")

        if (
            home_team is None
            or away_team is None
            or home_points is None
            or away_points is None
        ):
            skipped_games += 1
            continue

        predicted_winner = predict_winner(
            away_team,
            home_team,
            rating_lookup
        )

        if predicted_winner is None:

            missing_ratings.append(
                (
                    away_team,
                    home_team
                )
            )

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

    print()
    print("=" * 60)
    print(
        "2025 FBS POWER RATING BASELINE BACKTEST"
    )
    print("=" * 60)
    print()

    print(
        f"Historical games loaded: "
        f"{len(games)}"
    )

    print(
        f"FBS vs FBS games found: "
        f"{fbs_games_found}"
    )

    print(
        f"Games tested: "
        f"{total_games}"
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
        f"Skipped games: "
        f"{skipped_games}"
    )

    if total_games > 0:

        accuracy = (
            correct_predictions
            / total_games
        )

        print(
            f"Prediction accuracy: "
            f"{accuracy:.3%}"
        )

    else:

        print(
            "Prediction accuracy: N/A"
        )

    if missing_ratings:

        print()
        print(
            f"Games skipped because "
            f"of missing ratings: "
            f"{len(missing_ratings)}"
        )

        print()
        print(
            "First missing rating examples:"
        )

        for away_team, home_team in (
            missing_ratings[:10]
        ):
            print(
                f"  {away_team} @ {home_team}"
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

    print("=" * 60)


if __name__ == "__main__":
    backtest()
