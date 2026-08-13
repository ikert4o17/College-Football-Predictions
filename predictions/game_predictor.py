"""
Predict the outcome of an FBS game using power ratings.
"""

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RATINGS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "power_ratings_2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "game_predictions_2025.json"
)


# Initial home-field advantage.
HOME_FIELD_ADVANTAGE = 2.5

# Initial conversion from rating points
# to expected point margin.
RATING_TO_POINTS = 0.50


def load_ratings():
    """Load power ratings."""

    with RATINGS_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def build_rating_lookup(ratings):
    """Create a team rating lookup."""

    return {
        team["team"]: team
        for team in ratings
    }


def calculate_win_probability(
    rating_difference
):
    """
    Convert rating difference into
    approximate win probability.
    """

    return 1 / (
        1 + math.exp(
            -rating_difference / 8
        )
    )


def predict_game(
    away_team,
    home_team,
    rating_lookup
):
    """Predict one game."""

    away = rating_lookup.get(
        away_team
    )

    home = rating_lookup.get(
        home_team
    )

    if away is None or home is None:
        return None

    away_rating = away[
        "power_rating"
    ]

    home_rating = home[
        "power_rating"
    ]

    rating_difference = (
        home_rating
        - away_rating
    )

    adjusted_difference = (
        rating_difference
        + HOME_FIELD_ADVANTAGE
    )

    projected_margin = (
        adjusted_difference
        * RATING_TO_POINTS
    )

    home_win_probability = (
        calculate_win_probability(
            adjusted_difference
        )
    )

    away_win_probability = (
        1
        - home_win_probability
    )

    if home_win_probability >= 0.5:
        predicted_winner = home_team
    else:
        predicted_winner = away_team

    return {
        "away_team": away_team,
        "home_team": home_team,
        "away_rating": away_rating,
        "home_rating": home_rating,
        "rating_difference": round(
            rating_difference,
            2
        ),
        "home_field_advantage":
            HOME_FIELD_ADVANTAGE,
        "projected_margin": round(
            projected_margin,
            2
        ),
        "home_win_probability": round(
            home_win_probability,
            4
        ),
        "away_win_probability": round(
            away_win_probability,
            4
        ),
        "predicted_winner":
            predicted_winner,
    }


def main():
    """Run prediction examples."""

    ratings = load_ratings()

    rating_lookup = build_rating_lookup(
        ratings
    )

    examples = [
        ("Indiana", "Ohio State"),
        ("Air Force", "Colorado State"),
        ("Oregon", "Notre Dame"),
    ]

    predictions = []

    for away_team, home_team in examples:

        prediction = predict_game(
            away_team,
            home_team,
            rating_lookup
        )

        if prediction is not None:
            predictions.append(
                prediction
            )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            predictions,
            file,
            indent=4
        )

    print(
        f"Generated {len(predictions)} "
        f"game predictions."
    )

    for prediction in predictions:

        print(
            f"{prediction['away_team']} "
            f"@ "
            f"{prediction['home_team']}: "
            f"{prediction['predicted_winner']} "
            f"by "
            f"{abs(prediction['projected_margin']):.1f}"
        )


if __name__ == "__main__":
    main()
