"""
Week-by-week backtest framework for Project Gridiron.

This version establishes the weekly backtesting structure.

IMPORTANT:
The current version uses the existing 2025 power ratings
for predictions. It does NOT yet update ratings during
the season.

The next version will introduce dynamic weekly ratings.
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
    """Return True if the game is FBS vs FBS."""

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


def get_actual_winner(game):
    """Determine the actual winner."""

    home = game["home"]
    away = game["away"]

    home_points = home["points"]
    away_points = away["points"]

    if home_points > away_points:
        return home["team"]

    if away_points > home_points:
        return away["team"]

    return None


def group_games_by_week(games):
    """Group FBS games by week."""

    weekly_games = {}

    for game in games:

        if not is_fbs_vs_fbs(game):
            continue

        week = game.get("week")

        if week is None:
            continue

        if week not in weekly_games:
            weekly_games[week] = []

        weekly_games[week].append(game)

    return weekly_games


def backtest_week(
    week,
    games,
    ratings
):
    """Backtest one week."""

    total_games = 0
    correct_predictions = 0
    skipped_games = 0

    for game in games:

        home = game.get("home")
        away = game.get("away")

        if home is None or away is None:
            skipped_games += 1
            continue

        home_team = home.get("team")
        away_team = away.get("team")

        if (
            home_team is None
            or away_team is None
        ):
            skipped_games += 1
            continue

        predicted_winner = predict_winner(
            away_team,
            home_team,
            ratings
        )

        if predicted_winner is None:
            skipped_games += 1
            continue

        actual_winner = get_actual_winner(
            game
        )

        if actual_winner is None:
            skipped_games += 1
            continue

        total_games += 1

        if predicted_winner == actual_winner:
            correct_predictions += 1

    return {
        "week": week,
        "games": total_games,
        "correct": correct_predictions,
        "incorrect": (
            total_games
            - correct_predictions
        ),
        "skipped": skipped_games,
    }


def main():
    """Run the weekly backtest."""

    games = load_json(
        GAMES_FILE
    )

    ratings = load_json(
        RATINGS_FILE
    )

    rating_lookup = build_rating_lookup(
        ratings
    )

    weekly_games = group_games_by_week(
        games
    )

    print()
    print("=" * 70)
    print(
        "2025 WEEK-BY-WEEK BACKTEST"
    )
    print("=" * 70)
    print()

    print(
        f"Historical games loaded: "
        f"{len(games)}"
    )

    print(
        f"Power ratings loaded: "
        f"{len(ratings)}"
    )

    print(
        f"Weeks found: "
        f"{len(weekly_games)}"
    )

    print()

    total_games = 0
    total_correct = 0
    total_skipped = 0

    for week in sorted(
        weekly_games.keys()
    ):

        result = backtest_week(
            week,
            weekly_games[week],
            rating_lookup
        )

        total_games += result["games"]

        total_correct += result[
            "correct"
        ]

        total_skipped += result[
            "skipped"
        ]

        if result["games"] > 0:

            accuracy = (
                result["correct"]
                / result["games"]
            )

        else:

            accuracy = 0

        print(
            f"Week {week:>2}: "
            f"{result['correct']:>3}/"
            f"{result['games']:<3} "
            f"({accuracy:.1%}) "
            f"Skipped: "
            f"{result['skipped']}"
        )

    print()
    print("-" * 70)

    if total_games > 0:

        overall_accuracy = (
            total_correct
            / total_games
        )

    else:

        overall_accuracy = 0

    print(
        f"Total games tested: "
        f"{total_games}"
    )

    print(
        f"Correct predictions: "
        f"{total_correct}"
    )

    print(
        f"Incorrect predictions: "
        f"{total_games - total_correct}"
    )

    print(
        f"Skipped games: "
        f"{total_skipped}"
    )

    print(
        f"Overall accuracy: "
        f"{overall_accuracy:.3%}"
    )

    print()
    print(
        "NOTE: This version uses "
        "full-season 2025 ratings."
    )

    print(
        "Dynamic weekly rating updates "
        "will be added next."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
