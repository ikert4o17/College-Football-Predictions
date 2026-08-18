"""
Project Gridiron
Game Totals Calibration

Purpose
-------
Calibrate a simple game-total model using completed 2025 FBS-vs-FBS games.

The goal is to estimate expected combined points from team-level
Project Gridiron offense and defense ratings.

Inputs
------
data/processed/power_ratings_2025.json
data/processed/historical_games_2025.json

Output
------
data/processed/game_total_calibration_2025.json

Usage
-----
python -m ratings.calibrate_game_totals

Model
-----
actual_total
    =
intercept
    +
home_offense_coefficient * home_offense_score
    +
away_offense_coefficient * away_offense_score
    +
home_defense_coefficient * home_defense_score
    +
away_defense_coefficient * away_defense_score

This is a calibration model, not yet a true out-of-sample betting backtest.

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
    / "game_total_calibration_2025.json"
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


def safe_float(value, default=None):
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
# RATINGS
# ============================================================

def build_rating_lookup(records):
    """Build team rating lookup."""

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

        offense = safe_float(
            record.get(
                "offense_score"
            )
        )

        defense = safe_float(
            record.get(
                "defense_score"
            )
        )

        if (
            team
            and
            offense is not None
            and
            defense is not None
        ):

            lookup[
                team
            ] = {
                "offense_score":
                    offense,

                "defense_score":
                    defense,
            }

    return lookup


# ============================================================
# GAME EXTRACTION
# ============================================================

def extract_side(
    game,
    side
):
    """Extract nested team object."""

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
    """Extract points."""

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


# ============================================================
# BUILD DATASET
# ============================================================

def build_game_records(
    games,
    rating_lookup
):
    """Build completed 2025 FBS-vs-FBS total records."""

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

        actual_total = (
            home_points
            +
            away_points
        )

        records.append(
            {
                "game_id":
                    game.get(
                        "game_id"
                    ),

                "home_team":
                    home_team,

                "away_team":
                    away_team,

                "home_offense":
                    home_rating[
                        "offense_score"
                    ],

                "away_offense":
                    away_rating[
                        "offense_score"
                    ],

                "home_defense":
                    home_rating[
                        "defense_score"
                    ],

                "away_defense":
                    away_rating[
                        "defense_score"
                    ],

                "actual_total":
                    actual_total,
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
# LINEAR ALGEBRA
# ============================================================

def solve_linear_system(
    matrix,
    vector
):
    """Solve square system with Gaussian elimination."""

    size = len(
        vector
    )

    rows = []

    for row_index in range(
        size
    ):

        rows.append(
            [
                float(
                    matrix[
                        row_index
                    ][
                        column_index
                    ]
                )
                for column_index in range(
                    size
                )
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

    for pivot_index in range(
        size
    ):

        best_row = max(
            range(
                pivot_index,
                size
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

        for row_index in range(
            size
        ):

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
                pivot_row_value
                for current, pivot_row_value in zip(
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
            size
        ]
        for row_index in range(
            size
        )
    ]


# ============================================================
# REGRESSION
# ============================================================

def fit_regression(records):
    """Fit OLS total model."""

    columns = [
        [
            1.0
            for _ in records
        ],

        [
            record[
                "home_offense"
            ]
            for record in records
        ],

        [
            record[
                "away_offense"
            ]
            for record in records
        ],

        [
            record[
                "home_defense"
            ]
            for record in records
        ],

        [
            record[
                "away_defense"
            ]
            for record in records
        ],
    ]

    target = [
        record[
            "actual_total"
        ]
        for record in records
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
                y
                for x, y in zip(
                    column,
                    target
                )
            )
        )

    coefficients = solve_linear_system(
        xtx,
        xty,
    )

    return {
        "intercept":
            coefficients[0],

        "home_offense_coefficient":
            coefficients[1],

        "away_offense_coefficient":
            coefficients[2],

        "home_defense_coefficient":
            coefficients[3],

        "away_defense_coefficient":
            coefficients[4],
    }


# ============================================================
# EVALUATION
# ============================================================

def predict_total(
    record,
    model
):
    """Predict game total."""

    return (
        model[
            "intercept"
        ]
        +
        model[
            "home_offense_coefficient"
        ]
        *
        record[
            "home_offense"
        ]
        +
        model[
            "away_offense_coefficient"
        ]
        *
        record[
            "away_offense"
        ]
        +
        model[
            "home_defense_coefficient"
        ]
        *
        record[
            "home_defense"
        ]
        +
        model[
            "away_defense_coefficient"
        ]
        *
        record[
            "away_defense"
        ]
    )


def evaluate(
    records,
    model
):
    """Evaluate total calibration."""

    predictions = [
        predict_total(
            record,
            model
        )
        for record in records
    ]

    actuals = [
        record[
            "actual_total"
        ]
        for record in records
    ]

    return {
        "correlation":
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

        "actual_total_mean":
            mean(
                actuals
            ),

        "prediction_mean":
            mean(
                predictions
            ),
    }


# ============================================================
# MAIN
# ============================================================

def calibrate():
    """Run game-total calibration."""

    print("=" * 78)
    print("PROJECT GRIDIRON GAME TOTAL CALIBRATION")
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
            "Not enough games for total calibration."
        )

    model = fit_regression(
        records
    )

    metrics = evaluate(
        records,
        model
    )

    print("TOTAL MODEL")
    print("-" * 78)

    print(
        f"Intercept: "
        f"{model['intercept']:+.4f}"
    )

    print(
        f"Home offense coefficient: "
        f"{model['home_offense_coefficient']:+.4f}"
    )

    print(
        f"Away offense coefficient: "
        f"{model['away_offense_coefficient']:+.4f}"
    )

    print(
        f"Home defense coefficient: "
        f"{model['home_defense_coefficient']:+.4f}"
    )

    print(
        f"Away defense coefficient: "
        f"{model['away_defense_coefficient']:+.4f}"
    )

    print()

    print("MODEL PERFORMANCE")
    print("-" * 78)

    print(
        f"Correlation: "
        f"{metrics['correlation']:.4f}"
    )

    print(
        f"MAE: "
        f"{metrics['mae']:.2f}"
    )

    print(
        f"RMSE: "
        f"{metrics['rmse']:.2f}"
    )

    print(
        f"Average actual total: "
        f"{metrics['actual_total_mean']:.2f}"
    )

    print(
        f"Average predicted total: "
        f"{metrics['prediction_mean']:.2f}"
    )

    output = {
        "season":
            2025,

        "model_version":
            "game_total_calibration_v1",

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
