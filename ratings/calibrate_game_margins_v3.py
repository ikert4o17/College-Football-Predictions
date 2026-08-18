"""
Project Gridiron
Game Margin Calibration V3

Purpose
-------
Estimate two clean football quantities from completed 2025
FBS-vs-FBS games:

    1. scoreboard points per Project Gridiron rating point
    2. non-neutral home-field advantage

Unlike V2, V3 forces the intercept to zero.

Model
-----
actual_home_margin
    =
rating_gap_coefficient
    * (home_rating - away_rating)
    +
home_field_advantage
    * home_field_indicator

Where:

    home_field_indicator = 0 for neutral-site games
    home_field_indicator = 1 otherwise

This guarantees:

    equal teams + neutral field = projected margin of 0

Inputs
------
data/processed/power_ratings_2025.json
data/processed/historical_games_2025.json

Output
------
data/processed/game_margin_calibration_v3_2025.json

Usage
-----
python -m ratings.calibrate_game_margins_v3

This module makes zero CFBD API calls.
"""

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# FILES
# ============================================================

RATINGS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "power_ratings_2025.json"
)

GAMES_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "historical_games_2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "game_margin_calibration_v3_2025.json"
)


# ============================================================
# HELPERS
# ============================================================

def load_json(path):
    """Load JSON."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def safe_float(
    value,
    default=None
):
    """Safely convert value to float."""

    if value is None:
        return default

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return default


def mean(values):
    """Arithmetic mean."""

    if not values:
        return 0.0

    return sum(values) / len(values)


def standard_deviation(values):
    """Population standard deviation."""

    if not values:
        return 0.0

    average = mean(values)

    variance = (
        sum(
            (
                value
                -
                average
            )
            ** 2
            for value in values
        )
        /
        len(values)
    )

    return math.sqrt(
        variance
    )


def pearson_correlation(
    x_values,
    y_values
):
    """Pearson correlation."""

    if len(x_values) != len(y_values):
        return None

    if len(x_values) < 2:
        return None

    x_mean = mean(
        x_values
    )

    y_mean = mean(
        y_values
    )

    numerator = sum(
        (
            x
            -
            x_mean
        )
        *
        (
            y
            -
            y_mean
        )
        for x, y in zip(
            x_values,
            y_values
        )
    )

    x_variance = sum(
        (
            x
            -
            x_mean
        )
        ** 2
        for x in x_values
    )

    y_variance = sum(
        (
            y
            -
            y_mean
        )
        ** 2
        for y in y_values
    )

    denominator = math.sqrt(
        x_variance
        *
        y_variance
    )

    if denominator == 0:
        return None

    return (
        numerator
        /
        denominator
    )


def mean_absolute_error(
    predictions,
    actuals
):
    """Calculate MAE."""

    if not predictions:
        return None

    return (
        sum(
            abs(
                prediction
                -
                actual
            )
            for prediction, actual in zip(
                predictions,
                actuals
            )
        )
        /
        len(predictions)
    )


def root_mean_squared_error(
    predictions,
    actuals
):
    """Calculate RMSE."""

    if not predictions:
        return None

    mse = (
        sum(
            (
                prediction
                -
                actual
            )
            ** 2
            for prediction, actual in zip(
                predictions,
                actuals
            )
        )
        /
        len(predictions)
    )

    return math.sqrt(
        mse
    )


# ============================================================
# RATINGS
# ============================================================

def build_rating_lookup(records):
    """Build team -> rating lookup."""

    lookup = {}

    for record in records:

        if not isinstance(
            record,
            dict
        ):
            continue

        team = record.get(
            "team"
        )

        rating = safe_float(
            record.get(
                "power_rating"
            )
        )

        if (
            team
            and
            rating is not None
        ):
            lookup[
                team
            ] = rating

    return lookup


# ============================================================
# HISTORICAL GAME EXTRACTION
# ============================================================

def extract_side(
    game,
    side
):
    """Return nested home/away record."""

    value = game.get(
        side
    )

    if isinstance(
        value,
        dict
    ):
        return value

    return {}


def extract_team(
    game,
    side
):
    """Extract team name."""

    return extract_side(
        game,
        side
    ).get(
        "team"
    )


def extract_points(
    game,
    side
):
    """Extract team points."""

    return safe_float(
        extract_side(
            game,
            side
        ).get(
            "points"
        )
    )


def extract_classification(
    game,
    side
):
    """Extract classification."""

    value = extract_side(
        game,
        side
    ).get(
        "classification"
    )

    if value is None:
        return None

    return (
        str(
            value
        )
        .strip()
        .lower()
    )


def extract_neutral_site(game):
    """Return neutral-site flag."""

    return bool(
        game.get(
            "neutral_site",
            False,
        )
    )


# ============================================================
# DATASET
# ============================================================

def build_game_records(
    games,
    rating_lookup
):
    """Build completed 2025 FBS-vs-FBS calibration records."""

    records = []

    skipped_non_fbs = 0
    skipped_incomplete = 0
    skipped_missing_rating = 0
    skipped_bad_schema = 0

    for game in games:

        if not isinstance(
            game,
            dict
        ):
            skipped_bad_schema += 1
            continue

        if not game.get(
            "completed",
            False,
        ):
            skipped_incomplete += 1
            continue

        classification = game.get(
            "game_classification"
        )

        if (
            classification is not None
            and
            classification != "fbs_vs_fbs"
        ):
            skipped_non_fbs += 1
            continue

        if (
            extract_classification(
                game,
                "home"
            )
            !=
            "fbs"
            or
            extract_classification(
                game,
                "away"
            )
            !=
            "fbs"
        ):
            skipped_non_fbs += 1
            continue

        home_team = extract_team(
            game,
            "home"
        )

        away_team = extract_team(
            game,
            "away"
        )

        home_points = extract_points(
            game,
            "home"
        )

        away_points = extract_points(
            game,
            "away"
        )

        if (
            not home_team
            or
            not away_team
            or
            home_points is None
            or
            away_points is None
        ):
            skipped_bad_schema += 1
            continue

        if (
            home_team not in rating_lookup
            or
            away_team not in rating_lookup
        ):
            skipped_missing_rating += 1
            continue

        home_rating = rating_lookup[
            home_team
        ]

        away_rating = rating_lookup[
            away_team
        ]

        rating_gap = (
            home_rating
            -
            away_rating
        )

        actual_home_margin = (
            home_points
            -
            away_points
        )

        neutral_site = extract_neutral_site(
            game
        )

        home_field_indicator = (
            0.0
            if neutral_site
            else 1.0
        )

        records.append(
            {
                "game_id":
                    game.get(
                        "game_id"
                    ),

                "week":
                    game.get(
                        "week"
                    ),

                "home_team":
                    home_team,

                "away_team":
                    away_team,

                "rating_gap":
                    rating_gap,

                "actual_home_margin":
                    actual_home_margin,

                "neutral_site":
                    neutral_site,

                "home_field_indicator":
                    home_field_indicator,
            }
        )

    return {
        "records":
            records,

        "skipped_non_fbs":
            skipped_non_fbs,

        "skipped_incomplete":
            skipped_incomplete,

        "skipped_missing_rating":
            skipped_missing_rating,

        "skipped_bad_schema":
            skipped_bad_schema,
    }


# ============================================================
# 2x2 LINEAR REGRESSION
# ============================================================

def solve_2x2(
    matrix,
    vector
):
    """Solve 2x2 linear system."""

    a = float(
        matrix[0][0]
    )

    b = float(
        matrix[0][1]
    )

    c = float(
        matrix[1][0]
    )

    d = float(
        matrix[1][1]
    )

    e = float(
        vector[0]
    )

    f = float(
        vector[1]
    )

    determinant = (
        a
        *
        d
        -
        b
        *
        c
    )

    if abs(
        determinant
    ) < 1e-12:

        raise ValueError(
            "Regression matrix is singular."
        )

    x = (
        e
        *
        d
        -
        b
        *
        f
    ) / determinant

    y = (
        a
        *
        f
        -
        e
        *
        c
    ) / determinant

    return (
        x,
        y,
    )


def fit_regression(records):
    """
    Fit zero-intercept OLS:

        margin =
            beta_rating * rating_gap
            +
            beta_home * home_field
    """

    rating_gap = [
        record[
            "rating_gap"
        ]
        for record in records
    ]

    home_field = [
        record[
            "home_field_indicator"
        ]
        for record in records
    ]

    target = [
        record[
            "actual_home_margin"
        ]
        for record in records
    ]

    sum_x1_x1 = sum(
        value
        *
        value
        for value in rating_gap
    )

    sum_x1_x2 = sum(
        x1
        *
        x2
        for x1, x2 in zip(
            rating_gap,
            home_field
        )
    )

    sum_x2_x2 = sum(
        value
        *
        value
        for value in home_field
    )

    sum_x1_y = sum(
        x1
        *
        y
        for x1, y in zip(
            rating_gap,
            target
        )
    )

    sum_x2_y = sum(
        x2
        *
        y
        for x2, y in zip(
            home_field,
            target
        )
    )

    (
        rating_gap_coefficient,
        home_field_advantage,
    ) = solve_2x2(
        [
            [
                sum_x1_x1,
                sum_x1_x2,
            ],
            [
                sum_x1_x2,
                sum_x2_x2,
            ],
        ],
        [
            sum_x1_y,
            sum_x2_y,
        ],
    )

    return {
        "rating_gap_coefficient":
            rating_gap_coefficient,

        "home_field_advantage":
            home_field_advantage,
    }


# ============================================================
# EVALUATION
# ============================================================

def predict_home_margin(
    record,
    model
):
    """Predict home margin."""

    return (
        model[
            "rating_gap_coefficient"
        ]
        *
        record[
            "rating_gap"
        ]
        +
        model[
            "home_field_advantage"
        ]
        *
        record[
            "home_field_indicator"
        ]
    )


def evaluate(
    records,
    model
):
    """Evaluate V3 calibration."""

    predictions = [
        predict_home_margin(
            record,
            model
        )
        for record in records
    ]

    actuals = [
        record[
            "actual_home_margin"
        ]
        for record in records
    ]

    rating_gaps = [
        record[
            "rating_gap"
        ]
        for record in records
    ]

    neutral_records = [
        record
        for record in records
        if record[
            "neutral_site"
        ]
    ]

    non_neutral_records = [
        record
        for record in records
        if not record[
            "neutral_site"
        ]
    ]

    return {
        "raw_rating_gap_correlation":
            pearson_correlation(
                rating_gaps,
                actuals
            ),

        "prediction_correlation":
            pearson_correlation(
                predictions,
                actuals
            ),

        "mae":
            mean_absolute_error(
                predictions,
                actuals
            ),

        "rmse":
            root_mean_squared_error(
                predictions,
                actuals
            ),

        "actual_margin_mean":
            mean(
                actuals
            ),

        "prediction_mean":
            mean(
                predictions
            ),

        "actual_margin_std":
            standard_deviation(
                actuals
            ),

        "prediction_std":
            standard_deviation(
                predictions
            ),

        "neutral_games":
            len(
                neutral_records
            ),

        "non_neutral_games":
            len(
                non_neutral_records
            ),

        "neutral_actual_margin_mean":
            mean(
                [
                    record[
                        "actual_home_margin"
                    ]
                    for record in neutral_records
                ]
            ),

        "non_neutral_actual_margin_mean":
            mean(
                [
                    record[
                        "actual_home_margin"
                    ]
                    for record in non_neutral_records
                ]
            ),
    }


# ============================================================
# MAIN
# ============================================================

def calibrate():
    """Run V3 calibration."""

    print("=" * 78)
    print("PROJECT GRIDIRON GAME MARGIN CALIBRATION V3")
    print("=" * 78)
    print()

    if not RATINGS_FILE.exists():

        raise FileNotFoundError(
            f"Missing ratings file: "
            f"{RATINGS_FILE}"
        )

    if not GAMES_FILE.exists():

        raise FileNotFoundError(
            f"Missing games file: "
            f"{GAMES_FILE}"
        )

    ratings = load_json(
        RATINGS_FILE
    )

    games = load_json(
        GAMES_FILE
    )

    rating_lookup = build_rating_lookup(
        ratings
    )

    dataset = build_game_records(
        games,
        rating_lookup,
    )

    records = dataset[
        "records"
    ]

    print(
        f"Ratings loaded: "
        f"{len(rating_lookup)}"
    )

    print(
        f"Historical games loaded: "
        f"{len(games)}"
    )

    print(
        f"Usable FBS-vs-FBS games: "
        f"{len(records)}"
    )

    print()

    if len(records) < 20:

        raise ValueError(
            "Not enough calibration games."
        )

    model = fit_regression(
        records
    )

    metrics = evaluate(
        records,
        model
    )

    print("CALIBRATION MODEL")
    print("-" * 78)

    print(
        "projected home margin ="
    )

    print(
        f"    "
        f"{model['rating_gap_coefficient']:.4f} "
        f"* rating gap"
    )

    print(
        f"  + "
        f"{model['home_field_advantage']:.4f} "
        f"* home field"
    )

    print()

    print("INTERPRETATION")
    print("-" * 78)

    print(
        f"1 Project Gridiron rating point = "
        f"{model['rating_gap_coefficient']:.3f} "
        f"scoreboard points"
    )

    print(
        f"Estimated home-field advantage = "
        f"{model['home_field_advantage']:.2f} points"
    )

    print()

    print("MODEL PERFORMANCE")
    print("-" * 78)

    print(
        f"Raw rating-gap correlation: "
        f"{metrics['raw_rating_gap_correlation']:.4f}"
    )

    print(
        f"Prediction correlation: "
        f"{metrics['prediction_correlation']:.4f}"
    )

    print(
        f"MAE: "
        f"{metrics['mae']:.2f}"
    )

    print(
        f"RMSE: "
        f"{metrics['rmse']:.2f}"
    )

    print()

    print("HOME / NEUTRAL DIAGNOSTICS")
    print("-" * 78)

    print(
        f"Neutral games: "
        f"{metrics['neutral_games']}"
    )

    print(
        f"Non-neutral games: "
        f"{metrics['non_neutral_games']}"
    )

    print(
        f"Mean actual neutral-site home margin: "
        f"{metrics['neutral_actual_margin_mean']:+.2f}"
    )

    print(
        f"Mean actual non-neutral home margin: "
        f"{metrics['non_neutral_actual_margin_mean']:+.2f}"
    )

    output = {
        "season":
            2025,

        "model_version":
            "game_margin_calibration_v3",

        "games_tested":
            len(
                records
            ),

        "model":
            model,

        "metrics":
            metrics,

        "skipped":
            {
                "non_fbs":
                    dataset[
                        "skipped_non_fbs"
                    ],

                "incomplete":
                    dataset[
                        "skipped_incomplete"
                    ],

                "missing_rating":
                    dataset[
                        "skipped_missing_rating"
                    ],

                "bad_schema":
                    dataset[
                        "skipped_bad_schema"
                    ],
            },
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=4,
        )

    print()

    print(
        "Saved to:"
    )

    print(
        OUTPUT_FILE
    )

    return output


if __name__ == "__main__":
    calibrate()
