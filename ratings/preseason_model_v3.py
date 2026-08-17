"""
Project Gridiron
Combined Preseason Model Validation - Version 3

Version 3 uses historical SP+ as the baseline anchor instead of
Project Gridiron's own previous-season power rating.

Historical experiment:

    2024 SP+ baseline
        +
    returning production
        +
    incoming elite transfer talent
        -
    outgoing elite transfer talent
        +
    recruiting talent
        ->
    predict actual 2025 Project Gridiron rating

SP+ is standardized and mapped onto the Project Gridiron scale
before offseason adjustments are applied.

A model is considered valid only if it improves all three metrics
versus SP+ alone:

    correlation
    MAE
    RMSE

This module does NOT overwrite production ratings.
"""

import json
import itertools
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

RETURNING_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "returning_production_2025.json"
)

TRANSFER_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "transfer_talent_2025.json"
)

RECRUITING_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "recruiting_talent_2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "preseason_model_validation_2025_v3.json"
)


# ============================================================
# SEARCH SPACE
# ============================================================

RETURNING_MAX_POINTS = [
    0.0,
    0.5,
    1.0,
    1.5,
    2.0,
    3.0,
]

INCOMING_ELITE_POINTS = [
    0.0,
    0.25,
    0.50,
    0.75,
    1.00,
    1.25,
]

OUTGOING_ELITE_POINTS = [
    0.0,
    0.25,
    0.50,
    0.75,
    1.00,
    1.25,
]

RECRUITING_MAX_POINTS = [
    0.0,
    0.25,
    0.50,
    0.75,
    1.00,
    1.50,
]


RETURNING_CAP = 3.0
TRANSFER_CAP = 5.0
RECRUITING_CAP = 1.5


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

    if not values:
        return 0.0

    return (
        sum(values)
        /
        len(values)
    )


def standard_deviation(values):
    """Calculate population standard deviation."""

    if not values:
        return 0.0

    average = mean(
        values
    )

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


def clamp(
    value,
    minimum,
    maximum
):
    """Clamp a numeric value."""

    return max(
        minimum,
        min(
            value,
            maximum
        )
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


def z_score(
    value,
    average,
    std
):
    """Standardize one value."""

    if std == 0:
        return 0.0

    return (
        value
        -
        average
    ) / std


def get_returning_percent(record):
    """Read overall returning production percentage."""

    if not record:
        return 0.0

    overall = record.get(
        "overall",
        {}
    )

    value = safe_float(
        overall.get(
            "percent"
        )
    )

    if value is None:
        return 0.0

    return value


def build_analysis_records():
    """Build one historical team record."""

    gridiron_2024 = load_json(
        GRIDIRON_2024_FILE
    )

    gridiron_2025 = load_json(
        GRIDIRON_2025_FILE
    )

    sp_2024 = load_json(
        SP_2024_FILE
    )

    returning = load_json(
        RETURNING_FILE
    )

    transfers = load_json(
        TRANSFER_FILE
    )

    recruiting = load_json(
        RECRUITING_FILE
    )

    gridiron_2024_lookup = build_lookup(
        gridiron_2024
    )

    gridiron_2025_lookup = build_lookup(
        gridiron_2025
    )

    sp_lookup = build_lookup(
        sp_2024
    )

    returning_lookup = build_lookup(
        returning
    )

    transfer_lookup = build_lookup(
        transfers
    )

    recruiting_lookup = build_lookup(
        recruiting
    )

    teams = []

    for team_name in sorted(
        gridiron_2024_lookup
    ):

        if team_name not in gridiron_2025_lookup:
            continue

        if team_name not in sp_lookup:
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
            sp_lookup[
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

        returning_record = returning_lookup.get(
            team_name,
            {}
        )

        transfer_record = transfer_lookup.get(
            team_name,
            {}
        )

        recruiting_record = recruiting_lookup.get(
            team_name,
            {}
        )

        incoming = transfer_record.get(
            "incoming",
            {}
        )

        outgoing = transfer_record.get(
            "outgoing",
            {}
        )

        incoming_high_end = safe_float(
            incoming.get(
                "high_end_count"
            )
        )

        if incoming_high_end is None:
            incoming_high_end = 0.0

        outgoing_high_end = safe_float(
            outgoing.get(
                "high_end_count"
            )
        )

        if outgoing_high_end is None:
            outgoing_high_end = 0.0

        four_star_count = safe_float(
            recruiting_record.get(
                "four_star_count"
            )
        )

        if four_star_count is None:
            four_star_count = 0.0

        teams.append(
            {
                "team":
                    team_name,

                "gridiron_2024":
                    gridiron_2024_rating,

                "actual_2025":
                    gridiron_2025_rating,

                "sp_2024":
                    sp_rating,

                "returning_percent":
                    get_returning_percent(
                        returning_record
                    ),

                "incoming_high_end":
                    incoming_high_end,

                "outgoing_high_end":
                    outgoing_high_end,

                "four_star_count":
                    four_star_count,
            }
        )

    return teams


def calculate_context(teams):
    """Calculate all population context values."""

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

    returning_values = [
        team[
            "returning_percent"
        ]
        for team in teams
    ]

    recruiting_values = [
        team[
            "four_star_count"
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

        "returning_mean":
            mean(
                returning_values
            ),

        "returning_std":
            standard_deviation(
                returning_values
            ),

        "recruiting_min":
            min(
                recruiting_values
            ),

        "recruiting_max":
            max(
                recruiting_values
            ),
    }


def map_sp_to_gridiron(
    team,
    context
):
    """Map SP+ onto the Project Gridiron rating scale."""

    standardized_sp = z_score(
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

    return (
        context[
            "gridiron_mean"
        ]
        +
        standardized_sp
        *
        context[
            "gridiron_std"
        ]
    )


def returning_adjustment(
    team,
    context,
    max_points
):
    """Apply centered returning-production adjustment."""

    if max_points == 0:
        return 0.0

    std = context[
        "returning_std"
    ]

    if std == 0:
        return 0.0

    standardized = (
        (
            team[
                "returning_percent"
            ]
            -
            context[
                "returning_mean"
            ]
        )
        /
        std
    )

    adjustment = (
        standardized
        *
        max_points
    )

    return clamp(
        adjustment,
        -RETURNING_CAP,
        RETURNING_CAP
    )


def incoming_transfer_adjustment(
    team,
    points_per_player
):
    """Bonus for incoming 0.90+ transfers."""

    adjustment = (
        team[
            "incoming_high_end"
        ]
        *
        points_per_player
    )

    return clamp(
        adjustment,
        0.0,
        TRANSFER_CAP
    )


def outgoing_transfer_adjustment(
    team,
    points_per_player
):
    """Penalty for outgoing 0.90+ transfers."""

    adjustment = (
        -team[
            "outgoing_high_end"
        ]
        *
        points_per_player
    )

    return clamp(
        adjustment,
        -TRANSFER_CAP,
        0.0
    )


def recruiting_adjustment(
    team,
    context,
    max_points
):
    """Apply small positive recruiting bonus."""

    if max_points == 0:
        return 0.0

    minimum = context[
        "recruiting_min"
    ]

    maximum = context[
        "recruiting_max"
    ]

    if maximum == minimum:
        return 0.0

    normalized = (
        (
            team[
                "four_star_count"
            ]
            -
            minimum
        )
        /
        (
            maximum
            -
            minimum
        )
    )

    adjustment = (
        normalized
        *
        max_points
    )

    return clamp(
        adjustment,
        0.0,
        RECRUITING_CAP
    )


def project_team(
    team,
    context,
    returning_points,
    incoming_points,
    outgoing_points,
    recruiting_points
):
    """Generate one SP+-anchored preseason projection."""

    baseline = map_sp_to_gridiron(
        team,
        context
    )

    returning = returning_adjustment(
        team,
        context,
        returning_points
    )

    incoming = incoming_transfer_adjustment(
        team,
        incoming_points
    )

    outgoing = outgoing_transfer_adjustment(
        team,
        outgoing_points
    )

    recruiting = recruiting_adjustment(
        team,
        context,
        recruiting_points
    )

    total_adjustment = (
        returning
        +
        incoming
        +
        outgoing
        +
        recruiting
    )

    projected = (
        baseline
        +
        total_adjustment
    )

    return {
        "sp_baseline":
            baseline,

        "projected_rating":
            projected,

        "total_adjustment":
            total_adjustment,

        "returning_adjustment":
            returning,

        "incoming_transfer_adjustment":
            incoming,

        "outgoing_transfer_adjustment":
            outgoing,

        "recruiting_adjustment":
            recruiting,
    }


def evaluate_model(
    teams,
    context,
    returning_points,
    incoming_points,
    outgoing_points,
    recruiting_points
):
    """Evaluate one roster-adjustment combination."""

    predictions = []

    actuals = []

    for team in teams:

        result = project_team(
            team,
            context,
            returning_points,
            incoming_points,
            outgoing_points,
            recruiting_points
        )

        predictions.append(
            result[
                "projected_rating"
            ]
        )

        actuals.append(
            team[
                "actual_2025"
            ]
        )

    return {
        "returning_points":
            returning_points,

        "incoming_points":
            incoming_points,

        "outgoing_points":
            outgoing_points,

        "recruiting_points":
            recruiting_points,

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


def run_search(
    teams,
    context
):
    """Search roster-adjustment parameter combinations."""

    results = []

    combinations = itertools.product(
        RETURNING_MAX_POINTS,
        INCOMING_ELITE_POINTS,
        OUTGOING_ELITE_POINTS,
        RECRUITING_MAX_POINTS,
    )

    for (
        returning_points,
        incoming_points,
        outgoing_points,
        recruiting_points,
    ) in combinations:

        result = evaluate_model(
            teams,
            context,
            returning_points,
            incoming_points,
            outgoing_points,
            recruiting_points
        )

        results.append(
            result
        )

    return results


def model_improves_all(
    result,
    baseline_correlation,
    baseline_mae,
    baseline_rmse
):
    """Require improvement over SP+ on all three metrics."""

    return (
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


def improvement_score(
    result,
    baseline_correlation,
    baseline_mae,
    baseline_rmse
):
    """Combined ranking score for valid models."""

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

    return (
        correlation_gain
        *
        100.0
        +
        mae_gain
        +
        rmse_gain
    )


def build_team_results(
    teams,
    context,
    best
):
    """Build detailed team projections."""

    results = []

    for team in teams:

        projection = project_team(
            team,
            context,
            best[
                "returning_points"
            ],
            best[
                "incoming_points"
            ],
            best[
                "outgoing_points"
            ],
            best[
                "recruiting_points"
            ],
        )

        projected = projection[
            "projected_rating"
        ]

        actual = team[
            "actual_2025"
        ]

        results.append(
            {
                **team,

                **projection,

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
    """Run SP+-anchored combined preseason validation."""

    teams = build_analysis_records()

    if not teams:

        print(
            "No matching teams found."
        )
        return

    context = calculate_context(
        teams
    )

    baseline_predictions = [
        map_sp_to_gridiron(
            team,
            context
        )
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
        "PROJECT GRIDIRON PRESEASON MODEL V3"
    )

    print("=" * 72)

    print(
        f"Teams tested: "
        f"{len(teams)}"
    )

    print()

    print(
        "SP+ BASELINE PERFORMANCE"
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
        "ROSTER VARIABLES"
    )

    print("-" * 72)

    print(
        "Returning production: centered adjustment"
    )

    print(
        "Incoming 0.90+ transfers: positive bonus"
    )

    print(
        "Outgoing 0.90+ transfers: negative penalty"
    )

    print(
        "Four-star recruiting count: small positive bonus"
    )

    print()

    results = run_search(
        teams,
        context
    )

    valid_models = [
        result
        for result in results
        if model_improves_all(
            result,
            baseline_correlation,
            baseline_mae,
            baseline_rmse
        )
    ]

    print(
        f"Parameter combinations tested: "
        f"{len(results)}"
    )

    print(
        f"Models improving SP+ on all three metrics: "
        f"{len(valid_models)}"
    )

    print()

    if valid_models:

        for result in valid_models:

            result[
                "improvement_score"
            ] = improvement_score(
                result,
                baseline_correlation,
                baseline_mae,
                baseline_rmse
            )

        valid_models.sort(
            key=lambda result:
                result[
                    "improvement_score"
                ],
            reverse=True,
        )

        best = valid_models[0]

    else:

        print(
            "No roster-adjustment combination improved "
            "SP+ on correlation, MAE, and RMSE simultaneously."
        )

        print()

        # Still show the strongest candidates for diagnosis.
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
        "BEST MODEL"
    )

    print("-" * 72)

    print(
        f"Returning max points: "
        f"{best['returning_points']:.2f}"
    )

    print(
        f"Incoming elite transfer points/player: "
        f"{best['incoming_points']:.2f}"
    )

    print(
        f"Outgoing elite transfer penalty/player: "
        f"{best['outgoing_points']:.2f}"
    )

    print(
        f"Recruiting max bonus: "
        f"{best['recruiting_points']:.2f}"
    )

    print()

    print(
        f"SP+ baseline correlation: "
        f"{baseline_correlation:.4f}"
    )

    print(
        f"Model correlation: "
        f"{best['correlation']:.4f}"
    )

    print(
        f"Correlation change: "
        f"{best['correlation'] - baseline_correlation:+.4f}"
    )

    print()

    print(
        f"SP+ baseline MAE: "
        f"{baseline_mae:.2f}"
    )

    print(
        f"Model MAE: "
        f"{best['mae']:.2f}"
    )

    print(
        f"MAE improvement: "
        f"{baseline_mae - best['mae']:+.2f}"
    )

    print()

    print(
        f"SP+ baseline RMSE: "
        f"{baseline_rmse:.2f}"
    )

    print(
        f"Model RMSE: "
        f"{best['rmse']:.2f}"
    )

    print(
        f"RMSE improvement: "
        f"{baseline_rmse - best['rmse']:+.2f}"
    )

    print()

    print(
        "TOP 10 MODELS"
    )

    print("-" * 72)

    ranked_results = (
        valid_models
        if valid_models
        else results
    )

    for rank, result in enumerate(
        ranked_results[:10],
        start=1
    ):

        print(
            f"{rank}. "
            f"returning="
            f"{result['returning_points']:.2f}, "
            f"in="
            f"{result['incoming_points']:.2f}, "
            f"out="
            f"{result['outgoing_points']:.2f}, "
            f"recruit="
            f"{result['recruiting_points']:.2f}, "
            f"corr="
            f"{result['correlation']:.4f}, "
            f"MAE="
            f"{result['mae']:.2f}, "
            f"RMSE="
            f"{result['rmse']:.2f}"
        )

    team_results = build_team_results(
        teams,
        context,
        best
    )

    print()

    print(
        "BIGGEST POSITIVE ROSTER ADJUSTMENTS"
    )

    print("-" * 72)

    positive = sorted(
        team_results,
        key=lambda team:
            team[
                "total_adjustment"
            ],
        reverse=True,
    )

    for team in positive[:15]:

        print(
            f"{team['team']}: "
            f"SP baseline="
            f"{team['sp_baseline']:.2f}, "
            f"adjustment="
            f"{team['total_adjustment']:+.2f}, "
            f"projection="
            f"{team['projected_rating']:.2f}, "
            f"actual="
            f"{team['actual_2025']:.2f}"
        )

    print()

    print(
        "BIGGEST NEGATIVE ROSTER ADJUSTMENTS"
    )

    print("-" * 72)

    negative = sorted(
        team_results,
        key=lambda team:
            team[
                "total_adjustment"
            ]
    )

    for team in negative[:15]:

        print(
            f"{team['team']}: "
            f"SP baseline="
            f"{team['sp_baseline']:.2f}, "
            f"adjustment="
            f"{team['total_adjustment']:+.2f}, "
            f"projection="
            f"{team['projected_rating']:.2f}, "
            f"actual="
            f"{team['actual_2025']:.2f}"
        )

    print()

    print(
        "LARGEST MODEL ERRORS"
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
            f"projection="
            f"{team['projected_rating']:.2f}, "
            f"actual="
            f"{team['actual_2025']:.2f}, "
            f"error="
            f"{team['projection_error']:+.2f}, "
            f"roster_adj="
            f"{team['total_adjustment']:+.2f}"
        )

    output = {
        "season":
            2025,

        "version":
            3,

        "baseline":
            "SP+ mapped to Project Gridiron scale",

        "teams_tested":
            len(teams),

        "baseline_metrics": {
            "correlation":
                baseline_correlation,

            "mae":
                baseline_mae,

            "rmse":
                baseline_rmse,
        },

        "best_model":
            best,

        "valid_model_count":
            len(valid_models),

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
