```python
"""
True historical 2025 weekly backtest.

The model starts with information from the 2024 season and
then moves through the 2025 season one week at a time.

No 2025 final-season power ratings are used.

Process:

2024 results
    ↓
Initial 2025 ratings
    ↓
Predict Week 1
    ↓
Update from Week 1
    ↓
Predict Week 2
    ↓
Update from Week 2
    ↓
...
    ↓
Predict Week 16

This is intended to provide a much more realistic historical
simulation of how Project Gridiron would have performed during
the 2025 season.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

HISTORICAL_GAMES_2024 = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "historical_games_2024.json"
)

HISTORICAL_GAMES_2025 = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "historical_games_2025.json"
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

HOME_FIELD_ADVANTAGE = 2.5

UPDATE_RATE = 0.15

MAX_GAME_ADJUSTMENT = 5.0

BASE_RATING = 50.0


# ---------------------------------------------------------
# File loading
# ---------------------------------------------------------

def load_json(path):
    """Load JSON data from a file."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


# ---------------------------------------------------------
# Game helpers
# ---------------------------------------------------------

def is_fbs_vs_fbs(game):
    """Return True when both teams are FBS."""

    return (
        game.get("game_classification")
        == "fbs_vs_fbs"
    )


def get_team_name(game, side):
    """Return the team name for home or away."""

    team_data = game.get(side)

    if not team_data:
        return None

    return team_data.get("team")


def get_points(game, side):
    """Return points for home or away."""

    team_data = game.get(side)

    if not team_data:
        return None

    return team_data.get("points")


def get_margin(game):
    """
    Return home-team scoring margin.

    Positive = home team won.
    Negative = away team won.
    """

    home_points = get_points(
        game,
        "home"
    )

    away_points = get_points(
        game,
        "away"
    )

    if (
        home_points is None
        or away_points is None
    ):
        return None

    return (
        home_points
        - away_points
    )


def get_actual_winner(game):
    """Return the actual winning team."""

    home_team = get_team_name(
        game,
        "home"
    )

    away_team = get_team_name(
        game,
        "away"
    )

    margin = get_margin(game)

    if (
        home_team is None
        or away_team is None
        or margin is None
    ):
        return None

    if margin > 0:
        return home_team

    if margin < 0:
        return away_team

    return None


# ---------------------------------------------------------
# 2024 baseline
# ---------------------------------------------------------

def calculate_2024_team_performance(games):
    """
    Calculate a simple 2024 team performance rating.

    The rating is based on:

    - Win/loss results
    - Average scoring margin
    - Opponent quality

    This gives us a preseason starting point for 2025.
    """

    team_data = {}

    for game in games:

        if not is_fbs_vs_fbs(game):
            continue

        home_team = get_team_name(
            game,
            "home"
        )

        away_team = get_team_name(
            game,
            "away"
        )

        margin = get_margin(game)

        if (
            home_team is None
            or away_team is None
            or margin is None
        ):
            continue

        if home_team not in team_data:
            team_data[home_team] = {
                "games": 0,
                "wins": 0,
                "losses": 0,
                "margin": 0.0,
            }

        if away_team not in team_data:
            team_data[away_team] = {
                "games": 0,
                "wins": 0,
                "losses": 0,
                "margin": 0.0,
            }

        team_data[home_team]["games"] += 1
        team_data[away_team]["games"] += 1

        team_data[home_team]["margin"] += margin
        team_data[away_team]["margin"] -= margin

        if margin > 0:

            team_data[home_team]["wins"] += 1
            team_data[away_team]["losses"] += 1

        elif margin < 0:

            team_data[away_team]["wins"] += 1
            team_data[home_team]["losses"] += 1

    ratings = {}

    for team, data in team_data.items():

        games_played = data["games"]

        if games_played == 0:
            ratings[team] = BASE_RATING
            continue

        win_percentage = (
            data["wins"]
            / games_played
        )

        average_margin = (
            data["margin"]
            / games_played
        )

        # Convert 2024 performance into a rating
        # centered around 50.
        #
        # Win percentage contributes up to +/- 25.
        # Average margin contributes up to +/- 25.

        win_component = (
            win_percentage - 0.5
        ) * 50.0

        margin_component = (
            average_margin / 20.0
        ) * 25.0

        rating = (
            BASE_RATING
            + win_component
            + margin_component
        )

        ratings[team] = rating

    return ratings


# ---------------------------------------------------------
# Prediction
# ---------------------------------------------------------

def predict_winner(
    home_team,
    away_team,
    ratings
):
    """Predict the winner using current ratings."""

    home_rating = ratings.get(
        home_team
    )

    away_rating = ratings.get(
        away_team
    )

    if (
        home_rating is None
        or away_rating is None
    ):
        return None

    adjusted_home_rating = (
        home_rating
        + HOME_FIELD_ADVANTAGE
    )

    if adjusted_home_rating >= away_rating:
        return home_team

    return away_team


# ---------------------------------------------------------
# Weekly grouping
# ---------------------------------------------------------

def group_games_by_week(games):
    """Group FBS-vs-FBS games by week."""

    weekly_games = {}

    for game in games:

        if not is_fbs_vs_fbs(game):
            continue

        week = game.get("week")

        if week is None:
            continue

        weekly_games.setdefault(
            week,
            []
        ).append(game)

    return weekly_games


# ---------------------------------------------------------
# Rating updates
# ---------------------------------------------------------

def update_ratings_after_week(
    games,
    ratings
):
    """
    Update ratings after a complete week.

    All adjustments are calculated from the ratings that
    existed before the week started.
    """

    adjustments = {}

    starting_ratings = ratings.copy()

    for game in games:

        home_team = get_team_name(
            game,
            "home"
        )

        away_team = get_team_name(
            game,
            "away"
        )

        margin = get_margin(game)

        if (
            home_team is None
            or away_team is None
            or margin is None
        ):
            continue

        home_rating = starting_ratings.get(
            home_team
        )

        away_rating = starting_ratings.get(
            away_team
        )

        if (
            home_rating is None
            or away_rating is None
        ):
            continue

        expected_margin = (
            home_rating
            + HOME_FIELD_ADVANTAGE
            - away_rating
        )

        margin_error = (
            margin
            - expected_margin
        )

        adjustment = (
            margin_error
            * UPDATE_RATE
        )

        adjustment = max(
            -MAX_GAME_ADJUSTMENT,
            min(
                MAX_GAME_ADJUSTMENT,
                adjustment
            )
        )

        adjustments[home_team] = (
            adjustments.get(
                home_team,
                0.0
            )
            + adjustment
        )

        adjustments[away_team] = (
            adjustments.get(
                away_team,
                0.0
            )
            - adjustment
        )

    for team, adjustment in adjustments.items():

        ratings[team] = (
            ratings[team]
            + adjustment
        )

    return adjustments


# ---------------------------------------------------------
# Backtest one week
# ---------------------------------------------------------

def backtest_week(
    games,
    ratings
):
    """Predict all games using pre-week ratings."""

    correct = 0
    tested = 0
    skipped = 0

    for game in games:

        home_team = get_team_name(
            game,
            "home"
        )

        away_team = get_team_name(
            game,
            "away"
        )

        actual_winner = get_actual_winner(
            game
        )

        if (
            home_team is None
            or away_team is None
            or actual_winner is None
        ):
            skipped += 1
            continue

        prediction = predict_winner(
            home_team,
            away_team,
            ratings
        )

        if prediction is None:
            skipped += 1
            continue

        tested += 1

        if prediction == actual_winner:
            correct += 1

    return {
        "tested": tested,
        "correct": correct,
        "skipped": skipped,
    }


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    games_2024 = load_json(
        HISTORICAL_GAMES_2024
    )

    games_2025 = load_json(
        HISTORICAL_GAMES_2025
    )

    print()
    print("=" * 70)
    print(
        "2025 TRUE PRESEASON WEEKLY BACKTEST"
    )
    print("=" * 70)
    print()

    print(
        f"2024 historical games loaded: "
        f"{len(games_2024)}"
    )

    print(
        f"2025 historical games loaded: "
        f"{len(games_2025)}"
    )

    # -----------------------------------------------------
    # Build starting ratings ONLY from 2024.
    # -----------------------------------------------------

    ratings = (
        calculate_2024_team_performance(
            games_2024
        )
    )

    print(
        f"Initial 2024-based ratings: "
        f"{len(ratings)}"
    )

    # -----------------------------------------------------
    # Group 2025 games.
    # -----------------------------------------------------

    weekly_games = (
        group_games_by_week(
            games_2025
        )
    )

    print(
        f"Weeks found: "
        f"{len(weekly_games)}"
    )

    print()

    total_tested = 0
    total_correct = 0
    total_skipped = 0

    # -----------------------------------------------------
    # Simulate the season.
    # -----------------------------------------------------

    for week in sorted(
        weekly_games.keys()
    ):

        games = weekly_games[week]

        # Predict using ratings available BEFORE
        # this week's games.
        result = backtest_week(
            games,
            ratings
        )

        total_tested += result[
            "tested"
        ]

        total_correct += result[
            "correct"
        ]

        total_skipped += result[
            "skipped"
        ]

        if result["tested"]:

            accuracy = (
                result["correct"]
                / result["tested"]
            )

        else:

            accuracy = 0.0

        print(
            f"Week {week:>2}: "
            f"{result['correct']:>3}/"
            f"{result['tested']:<3} "
            f"({accuracy:.1%}) "
            f"Skipped: "
            f"{result['skipped']}"
        )

        # Update AFTER the predictions.
        adjustments = (
            update_ratings_after_week(
                games,
                ratings
            )
        )

        print(
            f"          "
            f"Teams updated: "
            f"{len(adjustments)}"
        )

    # -----------------------------------------------------
    # Final summary.
    # -----------------------------------------------------

    print()
    print("-" * 70)

    total_incorrect = (
        total_tested
        - total_correct
    )

    if total_tested:

        overall_accuracy = (
            total_correct
            / total_tested
        )

        accuracy_text = (
            f"{overall_accuracy:.3%}"
        )

    else:

        accuracy_text = "N/A"

    print(
        f"Games tested: "
        f"{total_tested}"
    )

    print(
        f"Correct predictions: "
        f"{total_correct}"
    )

    print(
        f"Incorrect predictions: "
        f"{total_incorrect}"
    )

    print(
        f"Skipped games: "
        f"{total_skipped}"
    )

    print(
        f"Prediction accuracy: "
        f"{accuracy_text}"
    )

    print()
    print(
        "Starting ratings source: "
        "2024 FBS-vs-FBS results"
    )

    print(
        f"Update rate: "
        f"{UPDATE_RATE}"
    )

    print(
        f"Maximum game adjustment: "
        f"{MAX_GAME_ADJUSTMENT}"
    )

    print(
        f"Home-field advantage: "
        f"{HOME_FIELD_ADVANTAGE}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
```
