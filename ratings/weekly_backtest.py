"""
Dynamic week-by-week backtest for Project Gridiron.

This version simulates the 2025 season one week at a time.

Process:

1. Load 2025 historical games.
2. Load the existing 2025 power ratings.
3. Group FBS-vs-FBS games by week.
4. Predict each week's games using the ratings available
   BEFORE that week's games.
5. After the week's games are completed, update the ratings
   using the actual results.
6. Repeat for the next week.

IMPORTANT:
The initial ratings are still based on the existing 2025
power-rating file. The goal of this version is to establish
a dynamic rating/backtesting framework without introducing
additional complexity all at once.
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


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

# How strongly actual game results influence the rating.
UPDATE_RATE = 0.15

# Maximum adjustment from a single game.
MAX_GAME_ADJUSTMENT = 5.0

# Home-field advantage added to the home team's rating
# when making a prediction.
HOME_FIELD_ADVANTAGE = 2.5


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
# Rating setup
# ---------------------------------------------------------

def build_rating_lookup(ratings):
    """
    Build a simple team -> rating dictionary.

    The existing power-rating file contains:

        team
        power_rating
        rank
        etc.
    """

    rating_lookup = {}

    for team in ratings:

        name = team.get("team")

        if name is None:
            continue

        rating_lookup[name] = float(
            team.get(
                "power_rating",
                50.0
            )
        )

    return rating_lookup


# ---------------------------------------------------------
# Game filtering
# ---------------------------------------------------------

def is_fbs_vs_fbs(game):
    """Return True for FBS-vs-FBS games."""

    return (
        game.get("game_classification")
        == "fbs_vs_fbs"
    )


def group_games_by_week(games):
    """Group FBS-vs-FBS games by week."""

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


# ---------------------------------------------------------
# Prediction
# ---------------------------------------------------------

def predict_winner(
    away_team,
    home_team,
    ratings
):
    """
    Predict the winner using the ratings available
    before the game.
    """

    away_rating = ratings.get(
        away_team
    )

    home_rating = ratings.get(
        home_team
    )

    if (
        away_rating is None
        or home_rating is None
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
# Actual result
# ---------------------------------------------------------

def get_actual_winner(game):
    """Return the actual winner."""

    home = game.get("home")
    away = game.get("away")

    if home is None or away is None:
        return None

    home_points = home.get("points")
    away_points = away.get("points")

    if (
        home_points is None
        or away_points is None
    ):
        return None

    if home_points > away_points:
        return home["team"]

    if away_points > home_points:
        return away["team"]

    return None


# ---------------------------------------------------------
# Margin
# ---------------------------------------------------------

def get_game_margin(game):
    """
    Return the home team's actual scoring margin.

    Example:

        Home 31
        Away 24

    returns +7.

    If:

        Home 17
        Away 28

    returns -11.
    """

    home = game.get("home")
    away = game.get("away")

    if home is None or away is None:
        return None

    home_points = home.get("points")
    away_points = away.get("points")

    if (
        home_points is None
        or away_points is None
    ):
        return None

    return (
        home_points
        - away_points
    )


# ---------------------------------------------------------
# Rating update
# ---------------------------------------------------------

def calculate_game_adjustment(
    predicted_rating,
    opponent_rating,
    actual_margin,
    home_team
):
    """
    Calculate a rating adjustment from the actual result.

    The adjustment is based primarily on the difference
    between the team's expected rating advantage and the
    actual scoring margin.

    This is intentionally conservative for v1.
    """

    expected_margin = (
        predicted_rating
        - opponent_rating
    )

    if home_team:
        expected_margin += (
            HOME_FIELD_ADVANTAGE
        )

    margin_error = (
        actual_margin
        - expected_margin
    )

    adjustment = (
        margin_error
        * UPDATE_RATE
    )

    # Prevent one game from moving a team too much.
    adjustment = max(
        -MAX_GAME_ADJUSTMENT,
        min(
            MAX_GAME_ADJUSTMENT,
            adjustment
        )
    )

    return adjustment


def update_ratings_after_week(
    games,
    ratings
):
    """
    Update ratings after all games in a week have been
    completed.

    Updates are calculated from the ratings that existed
    BEFORE the week began.

    This prevents one game in the same week from affecting
    another game's rating calculation.
    """

    adjustments = {}

    # -----------------------------------------------------
    # First calculate all adjustments.
    # -----------------------------------------------------

    for game in games:

        home = game.get("home")
        away = game.get("away")

        if home is None or away is None:
            continue

        home_team = home.get("team")
        away_team = away.get("team")

        if (
            home_team is None
            or away_team is None
        ):
            continue

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
            continue

        margin = get_game_margin(
            game
        )

        if margin is None:
            continue

        # Home team's adjustment.
        home_adjustment = (
            calculate_game_adjustment(
                predicted_rating=home_rating,
                opponent_rating=away_rating,
                actual_margin=margin,
                home_team=True
            )
        )

        # Away team's adjustment is the inverse.
        away_adjustment = (
            -home_adjustment
        )

        if home_team not in adjustments:
            adjustments[home_team] = 0.0

        if away_team not in adjustments:
            adjustments[away_team] = 0.0

        adjustments[home_team] += (
            home_adjustment
        )

        adjustments[away_team] += (
            away_adjustment
        )

    # -----------------------------------------------------
    # Apply all adjustments simultaneously.
    # -----------------------------------------------------

    for team, adjustment in adjustments.items():

        ratings[team] += adjustment

    return adjustments


# ---------------------------------------------------------
# Weekly backtest
# ---------------------------------------------------------

def backtest_week(
    week,
    games,
    ratings
):
    """
    Predict every game in a week using the ratings
    available BEFORE the week begins.
    """

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


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():
    """Run the dynamic weekly backtest."""

    games = load_json(
        GAMES_FILE
    )

    ratings_data = load_json(
        RATINGS_FILE
    )

    ratings = build_rating_lookup(
        ratings_data
    )

    weekly_games = group_games_by_week(
        games
    )

    print()
    print("=" * 70)
    print(
        "2025 DYNAMIC WEEK-BY-WEEK BACKTEST"
    )
    print("=" * 70)
    print()

    print(
        f"Historical games loaded: "
        f"{len(games)}"
    )

    print(
        f"Initial power ratings loaded: "
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

    # -----------------------------------------------------
    # Process each week.
    # -----------------------------------------------------

    for week in sorted(
        weekly_games.keys()
    ):

        games_this_week = (
            weekly_games[week]
        )

        # -------------------------------------------------
        # STEP 1:
        # Predict the entire week using ratings from the
        # previous week.
        # -------------------------------------------------

        result = backtest_week(
            week,
            games_this_week,
            ratings
        )

        total_games += result[
            "games"
        ]

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

            accuracy = 0.0

        print(
            f"Week {week:>2}: "
            f"{result['correct']:>3}/"
            f"{result['games']:<3} "
            f"({accuracy:.1%}) "
            f"Skipped: "
            f"{result['skipped']}"
        )

        # -------------------------------------------------
        # STEP 2:
        # AFTER all predictions are made, update the
        # ratings using that week's actual results.
        # -------------------------------------------------

        adjustments = (
            update_ratings_after_week(
                games_this_week,
                ratings
            )
        )

        print(
            f"          "
            f"Teams updated: "
            f"{len(adjustments)}"
        )

    # -----------------------------------------------------
    # Final results
    # -----------------------------------------------------

    print()
    print("-" * 70)

    if total_games > 0:

        overall_accuracy = (
            total_correct
            / total_games
        )

    else:

        overall_accuracy = 0.0

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
        "Dynamic rating updates were "
        "applied after every week."
    )

    print(
        f"Update rate: {UPDATE_RATE}"
    )

    print(
        f"Maximum single-game adjustment: "
        f"{MAX_GAME_ADJUSTMENT}"
    )

    print(
        f"Home-field advantage: "
        f"{HOME_FIELD_ADVANTAGE}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
