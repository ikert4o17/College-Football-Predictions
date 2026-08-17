"""
Validate whether blending Project Gridiron power ratings with
historical SP+ improves the preseason baseline.

Historical experiment:

    2024 Project Gridiron rating
    +
    2024 SP+ rating
        ->
    predict 2025 Project Gridiron rating

Because Project Gridiron and SP+ use different scales, both are
standardized before blending. The blended standardized score is
then mapped back onto the Project Gridiron rating scale.

This module tests multiple blend weights and compares:

- Correlation
- Mean Absolute Error
- Root Mean Squared Error

This module does NOT modify production ratings.
"""

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

GRIDIRON_2024_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "power_ratings_2024.json"
)

GRIDIRON_2025_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "power_ratings_2025.json"
)

SP_2024_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "sp_ratings"
    / "2024.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "sp_baseline_validation_2025.json"
)


SP_WEIGHTS = [
    0.00,
    0.10,
    0.20,
    0.30,
    0.40,
    0.50,
    0.60,
    0.70,
    0.80,
    0.90,
    1.00,
]


def load_json(path):
    """Load JSON data."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def build_lookup(records):
    """Build a team lookup."""

    return {
        record["team"]: record
        for record in records
        if record.get("team")
    }


def safe_float(value):
    """Safely convert a value to float."""

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return None


def mean(values):
    """Calculate arithmetic mean."""

    return (
        sum(values)
        /
        len(values)
    )


def standard_deviation(values):
    """Calculate population standard deviation."""

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
            x - x_mean
        )
        *
        (
            y - y_mean
        )
        for x, y in zip(
            x_values,
            y_values
        )
    )

    x_variance = sum(
        (
            x - x_mean
        )
        ** 2
        for x in x_values
    )

    y_variance = sum(
        (
            y - y_mean
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


def build_records():
    """Build matching historical team records."""

    gridiron_2024 = load_json(
        GRIDIRON_2024_FILE
    )

    gridiron_2025 = load_json(
        GRIDIRON_2025_FILE
    )

    sp_2024 = load_json(
        SP_2024_FILE
    )

    gridiron_2024_lookup = build_lookup(
        gridiron_2024
    )

    gridiron_2025_lookup = build_lookup(
        gridiron_2025
    )

    sp_2024_lookup = build_lookup(
        sp_2024
    )

    teams = []

    for team_name in sorted(
        gridiron_2024_lookup
    ):

        if (
            team_name
            not in gridiron_2025_lookup
        ):
            continue

        if (
            team_name
            not in sp_2024_lookup
        ):
            continue

        gridiron_2024_rating = safe_float(
            gridiron_2024_lookup[
                team_name
            ].get(
                "power_rating"
            )
        )

        gridiron_2025_rating = safe_float(
            gridiron_2025_lookup[
                team_name
            ].get(
                "power_rating"
            )
        )

        sp_rating = safe_float(
            sp_2024_lookup[
                team_name
            ].get(
                "rating"
            )
        )

        if (
            gridiron_2024_rating is None
            or gridiron_2025_rating is None
            or sp_rating is None
        ):
            continue

        teams.append(
            {
                "team":
                    team_name,

                "gridiron_2024":
                    gridiron_2024_rating,

                "sp_2024":
                    sp_rating,

                "actual_2025":
                    gridiron_2025_rating,
            }
        )

    return teams


def calculate_context(teams):
    """Calculate scale information for both rating systems."""

    gridiron_values = [
        team[
            "gridiron_2024"
        ]
        for team in teams
    ]

    sp_values = [
        team[
            "sp_2024"
        ]
        for team in teams
    ]

    return {
        "gridiron_mean":
            mean(
                gridiron_values
            ),

        "gridiron_std":
            standard_deviation(
                gridiron_values
            ),

        "sp_mean":
            mean(
                sp_values
            ),

        "sp_std":
            standard_deviation(
                sp_values
            ),
    }


def z_score(
    value,
    average,
    std
):
    """Convert a rating to standardized form."""

    if std == 0:
        return 0.0

    return (
        value
        -
        average
    ) / std


def map_to_gridiron_scale(
    standardized_value,
    context
):
    """Convert a standardized score back to Gridiron scale."""

    return (
        context[
            "gridiron_mean"
        ]
        +
        standardized_value
        *
        context[
            "gridiron_std"
        ]
    )


def project_team(
    team,
    context,
    sp_weight
):
    """Blend Project Gridiron and SP+."""

    gridiron_weight = (
        1.0
        -
        sp_weight
    )

    gridiron_z = z_score(
        team[
            "gridiron_2024"
        ],
        context[
            "gridiron_mean"
        ],
        context[
            "gridiron_std"
        ],
    )

    sp_z = z_score(
        team[
            "sp_2024"
        ],
        context[
            "sp_mean"
        ],
        context[
            "sp_std"
        ],
    )

    blended_z = (
        gridiron_z
        *
        gridiron_weight
        +
        sp_z
        *
        sp_weight
    )

    projected = map_to_gridiron_scale(
        blended_z,
        context
    )

    return projected


def evaluate_blend(
    teams,
    context,
    sp_weight
):
    """Evaluate one SP+ blend."""

    predictions = []

    actuals = []

    for team in teams:

        predictions.append(
            project_team(
                team,
                context,
                sp_weight
            )
        )

        actuals.append(
            team[
                "actual_2025"
            ]
        )

    return {
        "sp_weight":
            sp_weight,

        "gridiron_weight":
            (
                1.0
                -
                sp_weight
            ),

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
    }


def build_team_results(
    teams,
    context,
    best
):
    """Generate team-level results for best blend."""

    results = []

    for team in teams:

        projected = project_team(
            team,
            context,
            best[
                "sp_weight"
            ]
        )

        actual = team[
            "actual_2025"
        ]

        results.append(
            {
                **team,

                "projected_2025":
                    projected,

                "projection_error":
                    projected
                    -
                    actual,

                "absolute_error":
                    abs(
                        projected
                        -
                        actual
                    ),
            }
        )

    return results


def analyze():
    """Run SP+ baseline validation."""

    teams = build_records()

    if not teams:

        print(
            "No matching teams found."
        )
        return

    context = calculate_context(
        teams
    )

    baseline_predictions = [
        team[
            "gridiron_2024"
        ]
        for team in teams
    ]

    actuals = [
        team[
            "actual_2025"
        ]
        for team in teams
    ]

    baseline_correlation = (
        pearson_correlation(
            baseline_predictions,
            actuals
        )
    )

    baseline_mae = (
        mean_absolute_error(
            baseline_predictions,
            actuals
        )
    )

    baseline_rmse = (
        root_mean_squared_error(
            baseline_predictions,
            actuals
        )
    )

    print("=" * 72)

    print(
        "SP+ BASELINE BLEND VALIDATION"
    )

    print("=" * 72)

    print(
        f"Teams tested: "
        f"{len(teams)}"
    )

    print()

    print(
        "PROJECT GRIDIRON BASELINE"
    )

    print("-" * 72)

    print(
        f"Correlation: "
        f"{baseline_correlation:.4f}"
    )

    print(
        f"MAE: "
        f"{baseline_mae:.2f}"
    )

    print(
        f"RMSE: "
        f"{baseline_rmse:.2f}"
    )

    print()

    print(
        "RATING SCALE CONTEXT"
    )

    print("-" * 72)

    print(
        f"Gridiron mean: "
        f"{context['gridiron_mean']:.2f}"
    )

    print(
        f"Gridiron standard deviation: "
        f"{context['gridiron_std']:.2f}"
    )

    print(
        f"SP+ mean: "
        f"{context['sp_mean']:.2f}"
    )

    print(
        f"SP+ standard deviation: "
        f"{context['sp_std']:.2f}"
    )

    print()

    print(
        "BLEND TESTS"
    )

    print("-" * 72)

    results = []

    for sp_weight in SP_WEIGHTS:

        result = evaluate_blend(
            teams,
            context,
            sp_weight
        )

        results.append(
            result
        )

        print(
            f"Gridiron "
            f"{result['gridiron_weight'] * 100:.0f}% "
            f"/ SP+ "
            f"{result['sp_weight'] * 100:.0f}%: "
            f"corr="
            f"{result['correlation']:.4f}, "
            f"MAE="
            f"{result['mae']:.2f}, "
            f"RMSE="
            f"{result['rmse']:.2f}"
        )

    valid_results = [
        result
        for result in results
        if (
            result[
                "correlation"
            ]
            >
            baseline_correlation
            and
            result[
                "mae"
            ]
            <
            baseline_mae
            and
            result[
                "rmse"
            ]
            <
            baseline_rmse
        )
    ]

    print()

    print(
        f"Blends improving all three metrics: "
        f"{len(valid_results)}"
    )

    print()

    if valid_results:

        # Rank using a combined improvement score.
        for result in valid_results:

            correlation_gain = (
                result[
                    "correlation"
                ]
                -
                baseline_correlation
            )

            mae_gain = (
                baseline_mae
                -
                result[
                    "mae"
                ]
            )

            rmse_gain = (
                baseline_rmse
                -
                result[
                    "rmse"
                ]
            )

            result[
                "improvement_score"
            ] = (
                correlation_gain
                *
                100.0
                +
                mae_gain
                +
                rmse_gain
            )

        valid_results.sort(
            key=lambda result:
                result[
                    "improvement_score"
                ],
            reverse=True,
        )

        best = valid_results[0]

    else:

        results.sort(
            key=lambda result:
                (
                    result[
                        "mae"
                    ],
                    result[
                        "rmse"
                    ],
                    -result[
                        "correlation"
                    ],
                )
        )

        best = results[0]

    print(
        "BEST BLEND"
    )

    print("-" * 72)

    print(
        f"Project Gridiron weight: "
        f"{best['gridiron_weight'] * 100:.0f}%"
    )

    print(
        f"SP+ weight: "
        f"{best['sp_weight'] * 100:.0f}%"
    )

    print()

    print(
        f"Correlation: "
        f"{best['correlation']:.4f} "
        f"(change="
        f"{best['correlation'] - baseline_correlation:+.4f})"
    )

    print(
        f"MAE: "
        f"{best['mae']:.2f} "
        f"(change="
        f"{baseline_mae - best['mae']:+.2f})"
    )

    print(
        f"RMSE: "
        f"{best['rmse']:.2f} "
        f"(change="
        f"{baseline_rmse - best['rmse']:+.2f})"
    )

    team_results = build_team_results(
        teams,
        context,
        best
    )

    print()

    print(
        "LARGEST BASELINE CHANGES FROM SP+"
    )

    print("-" * 72)

    largest_changes = sorted(
        team_results,
        key=lambda team:
            abs(
                team[
                    "projected_2025"
                ]
                -
                team[
                    "gridiron_2024"
                ]
            ),
        reverse=True,
    )

    for team in largest_changes[:15]:

        change = (
            team[
                "projected_2025"
            ]
            -
            team[
                "gridiron_2024"
            ]
        )

        print(
            f"{team['team']}: "
            f"Gridiron="
            f"{team['gridiron_2024']:.2f}, "
            f"SP+="
            f"{team['sp_2024']:.2f}, "
            f"blend="
            f"{team['projected_2025']:.2f} "
            f"({change:+.2f}), "
            f"actual="
            f"{team['actual_2025']:.2f}"
        )

    print()

    print(
        "LARGEST BLENDED BASELINE ERRORS"
    )

    print("-" * 72)

    worst = sorted(
        team_results,
        key=lambda team:
            team[
                "absolute_error"
            ],
        reverse=True,
    )

    for team in worst[:15]:

        print(
            f"{team['team']}: "
            f"blend="
            f"{team['projected_2025']:.2f}, "
            f"actual="
            f"{team['actual_2025']:.2f}, "
            f"error="
            f"{team['projection_error']:+.2f}"
        )

    output = {
        "season":
            2025,

        "teams_tested":
            len(teams),

        "baseline": {
            "correlation":
                baseline_correlation,

            "mae":
                baseline_mae,

            "rmse":
                baseline_rmse,
        },

        "best_blend":
            best,

        "team_results":
            team_results,
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
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    analyze()
