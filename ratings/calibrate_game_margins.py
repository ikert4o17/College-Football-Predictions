"""
Project Gridiron
Game Margin Calibration

Purpose
-------
Calibrate Project Gridiron power-rating differences to actual football
point margins using completed 2025 FBS-vs-FBS games.

The provisional prediction layer currently assumes:

    1 rating point = 1 scoreboard point

That assumption has not been validated.

This module estimates:

    actual_home_margin
        =
    intercept
        +
    rating_gap_coefficient
        * (home_rating - away_rating)
        +
    home_field_coefficient
        * home_field_indicator

Neutral-site games receive home_field_indicator = 0.

Non-neutral games receive home_field_indicator = 1.

Inputs
------
data/processed/power_ratings_2025.json
data/processed/historical_games_2025.json

Alternative historical-game input:
data/raw/historical_games/2025.json

Output
------
data/processed/game_margin_calibration_2025.json

Usage
-----
python -m ratings.calibrate_game_margins

This module makes zero CFBD calls.
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

PREFERRED_GAMES_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "historical_games_2025.json"
)

ALTERNATE_GAMES_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "historical_games"
    / "2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "game_margin_calibration_2025.json"
)


# ============================================================
# HELPERS
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
    """Safely convert to float."""

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


def variance(values):
    """Population variance."""

    if not values:
        return 0.0

    average = mean(values)

    return (
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


def standard_deviation(values):
    """Population standard deviation."""

    return math.sqrt(
        variance(values)
    )


def pearson_correlation(
    x_values,
    y_values
):
    """Pearson correlation."""

    if (
        len(x_values)
        !=
        len(y_values)
    ):
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

    return numerator / denominator


def mean_absolute_error(
    predictions,
    actuals
):
    """MAE."""

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
    """RMSE."""

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
# FILE RESOLUTION
# ============================================================

def resolve_games_file():
    """Resolve historical-game file."""

    if PREFERRED_GAMES_FILE.exists():
        return PREFERRED_GAMES_FILE

    if ALTERNATE_GAMES_FILE.exists():
        return ALTERNATE_GAMES_FILE

    raise FileNotFoundError(
        "No 2025 historical game file was found."
    )


# ============================================================
# LOOKUPS
# ============================================================

def build_rating_lookup(records):
    """Build team -> power rating lookup."""

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
# GAME FIELD EXTRACTION
# ============================================================

def first_available(
    record,
    keys
):
    """Return first available field."""

    for key in keys:

        if key in record:

            value = record.get(
                key
            )

            if value is not None:
                return value

    return None


def extract_home_team(game):
    """Extract home team."""

    return first_available(
        game,
        [
            "home_team",
            "homeTeam",
            "home",
        ],
    )


def extract_away_team(game):
    """Extract away team."""

    return first_available(
        game,
        [
            "away_team",
            "awayTeam",
            "away",
        ],
    )


def extract_home_points(game):
    """Extract home score."""

    return safe_float(
        first_available(
            game,
            [
                "home_points",
                "homePoints",
                "home_score",
            ],
        )
    )


def extract_away_points(game):
    """Extract away score."""

    return safe_float(
        first_available(
            game,
            [
                "away_points",
                "awayPoints",
                "away_score",
            ],
        )
    )


def extract_neutral_site(game):
    """Extract neutral-site flag."""

    value = first_available(
        game,
        [
            "neutral_site",
            "neutralSite",
        ],
    )

    if isinstance(
        value,
        bool
    ):
        return value

    if value is None:
        return False

    return (
        str(
            value
        )
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "y",
        }
    )


def extract_home_classification(game):
    """Extract home classification if present."""

    value = first_available(
        game,
        [
            "home_classification",
            "homeClassification",
        ],
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
    """Extract away classification if present."""

    value = first_available(
        game,
        [
            "away_classification",
            "awayClassification",
        ],
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


# ============================================================
# DATASET
# ============================================================

def build_game_records(
    games,
    rating_lookup
):
    """Build completed 2025 FBS-vs-FBS calibration records."""

    records = []

    skipped_missing_rating = 0

    skipped_incomplete = 0

    skipped_non_fbs = 0

    for game in games:

        if not isinstance(
            game,
            dict
        ):
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
            skipped_incomplete += 1
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
            home_classification is not None
            and
            away_classification is not None
            and
            (
                home_classification != "fbs"
                or
                away_classification != "fbs"
            )
        ):
            skipped_non_fbs += 1
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

        neutral_site = (
            extract_neutral_site(
                game
            )
        )

        home_field_indicator = (
            0.0
            if neutral_site
            else 1.0
        )

        records.append(
            {
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

                "home_field_indicator":
                    home_field_indicator,

                "neutral_site":
                    neutral_site,

                "actual_home_margin":
                    actual_home_margin,
            }
        )

    return {
        "records":
            records,

        "skipped_missing_rating":
            skipped_missing_rating,

        "skipped_incomplete":
            skipped_incomplete,

        "skipped_non_fbs":
            skipped_non_fbs,
    }


# ============================================================
# MULTIPLE LINEAR REGRESSION
# ============================================================

def solve_3x3(
    matrix,
    vector
):
    """
    Solve 3x3 linear system with Gaussian elimination.

    Used for:

        intercept
        rating-gap coefficient
        home-field coefficient
    """

    augmented = [
        [
            float(
                matrix[row][column]
            )
            for column in range(3)
        ]
        +
        [
            float(
                vector[row]
            )
        ]
        for row in range(3)
    ]

    for pivot in range(3):

        best_row = max(
            range(
                pivot,
                3
            ),
            key=lambda row:
                abs(
                    augmented[row][pivot]
                ),
        )

        if abs(
            augmented[
                best_row
            ][
                pivot
            ]
        ) < 1e-12:

            raise ValueError(
                "Regression matrix is singular."
            )

        augmented[
            pivot
        ], augmented[
            best_row
        ] = (
            augmented[
                best_row
            ],
            augmented[
                pivot
            ],
        )

        pivot_value = augmented[
            pivot
        ][
            pivot
        ]

        augmented[
            pivot
        ] = [
            value
            /
            pivot_value
            for value in augmented[
                pivot
            ]
        ]

        for row in range(3):

            if row == pivot:
                continue

            factor = augmented[
                row
            ][
                pivot
            ]

            augmented[
                row
            ] = [
                current
                -
                factor
                *
                pivot_value_row
                for current, pivot_value_row in zip(
                    augmented[
                        row
                    ],
                    augmented[
                        pivot
                    ],
                )
            ]

    return [
        augmented[
            row
        ][
            3
        ]
        for row in range(3)
    ]


def fit_regression(records):
    """Fit OLS regression with intercept."""

    x0 = [
        1.0
        for _ in records
    ]

    x1 = [
        record[
            "rating_gap"
        ]
        for record in records
    ]

    x2 = [
        record[
            "home_field_indicator"
        ]
        for record in records
    ]

    y = [
        record[
            "actual_home_margin"
        ]
        for record in records
    ]

    columns = [
        x0,
        x1,
        x2,
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
                x
                *
                target
                for x, target in zip(
                    column,
                    y
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

def predict_record(
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


def evaluate(records, model):
    """Evaluate calibration."""

    predictions = [
        predict_record(
            record,
            model,
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

    return {
        "prediction_correlation":
            pearson_correlation(
                predictions,
                actuals,
            ),

        "raw_rating_gap_correlation":
            pearson_correlation(
                rating_gaps,
                actuals,
            ),

        "mae":
            mean_absolute_error(
                predictions,
                actuals,
            ),

        "rmse":
            root_mean_squared_error(
                predictions,
                actuals,
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
    """Run 2025 margin calibration."""

    if not RATINGS_FILE.exists():

        raise FileNotFoundError(
            f"Missing ratings file: "
            f"{RATINGS_FILE}"
        )

    games_file = resolve_games_file()

    ratings = load_json(
        RATINGS_FILE
    )

    games = load_json(
        games_file
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

    if len(records) < 20:

        raise ValueError(
            "Not enough completed rated games "
            "for margin calibration."
        )

    model = fit_regression(
        records
    )

    metrics = evaluate(
        records,
        model,
    )

    output = {
        "season":
            2025,

        "games_file":
            str(
                games_file
            ),

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
                "missing_rating":
                    dataset[
                        "skipped_missing_rating"
                    ],

                "incomplete":
                    dataset[
                        "skipped_incomplete"
                    ],

                "non_fbs":
                    dataset[
                        "skipped_non_fbs"
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

    print("=" * 78)

    print(
        "PROJECT GRIDIRON GAME MARGIN CALIBRATION"
    )

    print("=" * 78)

    print()

    print(
        f"Games tested: "
        f"{len(records)}"
    )

    print(
        f"Ratings loaded: "
        f"{len(rating_lookup)}"
    )

    print(
        f"Historical game file: "
        f"{games_file}"
    )

    print()

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
        f"* rating gap"
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
        f"1 Project Gridiron rating point "
        f"= approximately "
        f"{model['rating_gap_coefficient']:.3f} "
        f"scoreboard points"
    )

    print(
        f"Estimated non-neutral home-field value "
        f"= {model['home_field_coefficient']:.2f} points"
    )

    print(
        f"Regression intercept "
        f"= {model['intercept']:+.2f}"
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

    print()

    print(
        "SKIPPED RECORDS"
    )

    print("-" * 78)

    print(
        f"Missing rating: "
        f"{dataset['skipped_missing_rating']}"
    )

    print(
        f"Incomplete game: "
        f"{dataset['skipped_incomplete']}"
    )

    print(
        f"Non-FBS: "
        f"{dataset['skipped_non_fbs']}"
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
