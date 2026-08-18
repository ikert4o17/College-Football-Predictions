"""
Project Gridiron
Game Margin Calibration V2

Purpose
-------
Calibrate Project Gridiron power-rating differences to actual game
margins using completed 2025 FBS-vs-FBS games.

The processed historical game schema stores team information inside:

    game["home"]
    game["away"]

Example:

    {
        "home": {
            "team": "Kansas State",
            "classification": "fbs",
            "points": 21
        },
        "away": {
            "team": "Iowa State",
            "classification": "fbs",
            "points": 24
        },
        "neutral_site": true,
        "game_classification": "fbs_vs_fbs"
    }

Model
-----
actual_home_margin
    =
intercept
    +
rating_gap_coefficient
    * (home_rating - away_rating)
    +
home_field_coefficient
    * home_field_indicator

Where:

    home_field_indicator = 0 for neutral-site games
    home_field_indicator = 1 otherwise

Inputs
------
data/processed/power_ratings_2025.json
data/processed/historical_games_2025.json

Output
------
data/processed/game_margin_calibration_2025.json

Usage
-----
python -m ratings.calibrate_game_margins_v2

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
    / "game_margin_calibration_2025.json"
)


# ============================================================
# GENERIC HELPERS
# ============================================================

def load_json(path):
    """Load JSON file."""

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
    """Calculate Pearson correlation."""

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

    if not isinstance(
        records,
        list
    ):
        return lookup

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
    """Extract nested home or away object."""

    value = game.get(
        side
    )

    if isinstance(
        value,
        dict
    ):
        return value

    return {}


def extract_home_team(game):
    """Extract home team name."""

    return extract_side(
        game,
        "home"
    ).get(
        "team"
    )


def extract_away_team(game):
    """Extract away team name."""

    return extract_side(
        game,
        "away"
    ).get(
        "team"
    )


def extract_home_points(game):
    """Extract home points."""

    return safe_float(
        extract_side(
            game,
            "home"
        ).get(
            "points"
        )
    )


def extract_away_points(game):
    """Extract away points."""

    return safe_float(
        extract_side(
            game,
            "away"
        ).get(
            "points"
        )
    )


def extract_home_classification(game):
    """Extract home classification."""

    value = extract_side(
        game,
        "home"
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


def extract_away_classification(game):
    """Extract away classification."""

    value = extract_side(
        game,
        "away"
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
    """Extract neutral-site flag."""

    return bool(
        game.get(
            "neutral_site",
            False,
        )
    )


# ============================================================
# BUILD CALIBRATION DATASET
# ============================================================

def build_game_records(
    games,
    rating_lookup
):
    """Build completed 2025 FBS-vs-FBS calibration records."""

    records = []

    skipped_incomplete = 0
    skipped_non_fbs = 0
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

        # Prefer the processor's explicit classification.

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

        home_classification = (
            extract_home_classification(
                game
            )
        )

        away_classification = (
            extract_away_classification(
                game
            )
        )

        if (
            home_classification != "fbs"
            or
            away_classification != "fbs"
        ):
            skipped_non_fbs += 1
            continue

        home_team = extract_home_team(
            game
        )

        away_team = extract_away_team(
            game
        )

        home_points = extract_home_points(
            game
        )

        away_points = extract_away_points(
            game
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

                "home_rating":
                    home_rating,

                "away_rating":
                    away_rating,

                "rating_gap":
                    rating_gap,

                "neutral_site":
                    neutral_site,

                "home_field_indicator":
                    home_field_indicator,

                "home_points":
                    home_points,

                "away_points":
                    away_points,

                "actual_home_margin":
                    actual_home_margin,
            }
        )

    return {
        "records":
            records,

        "skipped_incomplete":
            skipped_incomplete,

        "skipped_non_fbs":
            skipped_non_fbs,

        "skipped_missing_rating":
            skipped_missing_rating,

        "skipped_bad_schema":
            skipped_bad_schema,
    }


# ============================================================
# 3x3 LINEAR SYSTEM
# ============================================================

def solve_3x3(
    matrix,
    vector
):
    """Solve a 3x3 linear system using Gaussian elimination."""

    rows = []

    for row_index in range(3):

        rows.append(
            [
                float(
                    matrix[
                        row_index
                    ][
                        column_index
                    ]
                )
                for column_index in range(3)
            ]
            +
            [
                float(
                    vector[
                        row_index
                    ]
                )
            ]
        )

    for pivot_index in range(3):

        best_row = max(
            range(
                pivot_index,
                3
            ),
            key=lambda row_index:
                abs(
                    rows[
                        row_index
                    ][
                        pivot_index
                    ]
                ),
        )

        if abs(
            rows[
                best_row
            ][
                pivot_index
            ]
        ) < 1e-12:

            raise ValueError(
                "Regression matrix is singular."
            )

        rows[
            pivot_index
        ], rows[
            best_row
        ] = (
            rows[
                best_row
            ],
            rows[
                pivot_index
            ],
        )

        pivot_value = rows[
            pivot_index
        ][
            pivot_index
        ]

        rows[
            pivot_index
        ] = [
            value
            /
            pivot_value
            for value in rows[
                pivot_index
            ]
        ]

        for row_index in range(3):

            if row_index == pivot_index:
                continue

            factor = rows[
                row_index
            ][
                pivot_index
            ]

            rows[
                row_index
            ] = [
                current
                -
                factor
                *
                pivot_value_row
                for current, pivot_value_row in zip(
                    rows[
                        row_index
                    ],
                    rows[
                        pivot_index
                    ],
                )
            ]

    return [
        rows[
            row_index
        ][
            3
        ]
        for row_index in range(3)
    ]


# ============================================================
# REGRESSION
# ============================================================

def fit_regression(records):
    """Fit OLS regression with intercept."""

    intercept_column = [
        1.0
        for _ in records
    ]

    rating_gap_column = [
        record[
            "rating_gap"
        ]
        for record in records
    ]

    home_field_column = [
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

    columns = [
        intercept_column,
        rating_gap_column,
        home_field_column,
    ]

    xtx = []

    for column_a in columns:

        row = []

        for column_b in columns:

            row.append(
                sum(
                    a
                    *
                    b
                    for a, b in zip(
                        column_a,
                        column_b
                    )
                )
            )

        xtx.append(
            row
        )

    xty = []

    for column in columns:

        xty.append(
            sum(
                value
                *
                target_value
                for value, target_value in zip(
                    column,
                    target
                )
            )
        )

    (
        intercept,
        rating_gap_coefficient,
        home_field_coefficient,
    ) = solve_3x3(
        xtx,
        xty,
    )

    return {
        "intercept":
            intercept,

        "rating_gap_coefficient":
            rating_gap_coefficient,

        "home_field_coefficient":
            home_field_coefficient,
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
            "intercept"
        ]
        +
        model[
            "rating_gap_coefficient"
        ]
        *
        record[
            "rating_gap"
        ]
        +
        model[
            "home_field_coefficient"
        ]
        *
        record[
            "home_field_indicator"
        ]
    )


def evaluate_model(
    records,
    model
):
    """Evaluate fitted calibration model."""

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

    raw_rating_gaps = [
        record[
            "rating_gap"
        ]
        for record in records
    ]

    return {
        "raw_rating_gap_correlation":
            pearson_correlation(
                raw_rating_gaps,
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

        "actual_margin_std":
            standard_deviation(
                actuals
            ),

        "prediction_mean":
            mean(
                predictions
            ),

        "prediction_std":
            standard_deviation(
                predictions
            ),
    }


# ============================================================
# MAIN
# ============================================================

def calibrate():
    """Run V2 margin calibration."""

    print("=" * 78)
    print("PROJECT GRIDIRON GAME MARGIN CALIBRATION V2")
    print("=" * 78)
    print()

    if not RATINGS_FILE.exists():

        raise FileNotFoundError(
            f"Missing ratings file: "
            f"{RATINGS_FILE}"
        )

    if not GAMES_FILE.exists():

        raise FileNotFoundError(
            f"Missing historical games file: "
            f"{GAMES_FILE}"
        )

    ratings = load_json(
        RATINGS_FILE
    )

    games = load_json(
        GAMES_FILE
    )

    print(
        f"Rating records loaded: "
        f"{len(ratings)}"
    )

    print(
        f"Historical game records loaded: "
        f"{len(games)}"
    )

    print()

    rating_lookup = build_rating_lookup(
        ratings
    )

    dataset = build_game_records(
        games,
        rating_lookup
    )

    records = dataset[
        "records"
    ]

    print(
        "CALIBRATION DATASET"
    )

    print("-" * 78)

    print(
        f"Usable completed FBS-vs-FBS games: "
        f"{len(records)}"
    )

    print(
        f"Skipped non-FBS games: "
        f"{dataset['skipped_non_fbs']}"
    )

    print(
        f"Skipped incomplete games: "
        f"{dataset['skipped_incomplete']}"
    )

    print(
        f"Skipped missing ratings: "
        f"{dataset['skipped_missing_rating']}"
    )

    print(
        f"Skipped bad schema: "
        f"{dataset['skipped_bad_schema']}"
    )

    print()

    if len(records) < 20:

        raise ValueError(
            "Not enough usable completed FBS-vs-FBS "
            "games for calibration."
        )

    model = fit_regression(
        records
    )

    metrics = evaluate_model(
        records,
        model
    )

    print(
        "CALIBRATION MODEL"
    )

    print("-" * 78)

    print(
        "actual home margin ="
    )

    print(
        f"    {model['intercept']:+.4f}"
    )

    print(
        f"  + {model['rating_gap_coefficient']:.4f} "
        f"* Project Gridiron rating gap"
    )

    print(
        f"  + {model['home_field_coefficient']:.4f} "
        f"* home field"
    )

    print()

    print(
        "INTERPRETATION"
    )

    print("-" * 78)

    print(
        f"1 Project Gridiron rating point = "
        f"{model['rating_gap_coefficient']:.3f} "
        f"scoreboard points"
    )

    print(
        f"Estimated home-field advantage = "
        f"{model['home_field_coefficient']:.2f} points"
    )

    print(
        f"Intercept = "
        f"{model['intercept']:+.2f}"
    )

    print()

    print(
        "MODEL PERFORMANCE"
    )

    print("-" * 78)

    print(
        f"Raw rating-gap correlation: "
        f"{metrics['raw_rating_gap_correlation']:.4f}"
    )

    print(
        f"Calibrated prediction correlation: "
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

    output = {
        "season":
            2025,

        "model_version":
            "game_margin_calibration_v2",

        "games_tested":
            len(records),

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
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=4
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
