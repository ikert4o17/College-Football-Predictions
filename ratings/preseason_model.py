"""
Project Gridiron
Combined Preseason Model Validation - Version 2

This version fixes the scaling problem from the first combined model.

Core principles:

1. Previous-season power rating remains the anchor.
2. Returning production is centered around the national average.
3. Incoming elite transfers create bonuses, not penalties for teams with none.
4. Outgoing elite transfers create penalties.
5. Recruiting creates only a small positive bonus.
6. Individual adjustments are capped to realistic point ranges.
7. A model must improve:
       correlation
       MAE
       RMSE
   before it can be considered better than the baseline.

Historical validation:

    2024 power rating
        ->
    2025 preseason projection
        ->
    actual 2025 power rating

Returning snaps are still not included historically because
we do not have a comparable 2025 snap dataset.

This module does NOT overwrite production power ratings.
"""

import json
import itertools
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


RATINGS_2024_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "power_ratings_2024.json"
)

RATINGS_2025_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "power_ratings_2025.json"
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

DRAFT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "draft_losses_2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "preseason_model_validation_2025_v2.json"
)


# ============================================================
# SEARCH SPACE
# ============================================================

RETURNING_MAX_POINTS = [
    0.0,
    1.0,
    2.0,
    3.0,
    4.0,
]

INCOMING_ELITE_POINTS = [
    0.0,
    0.25,
    0.50,
    0.75,
    1.00,
]

OUTGOING_ELITE_POINTS = [
    0.0,
    0.25,
    0.50,
    0.75,
    1.00,
]

RECRUITING_MAX_POINTS = [
    0.0,
    0.5,
    1.0,
    1.5,
    2.0,
]


RETURNING_CAP = 4.0
TRANSFER_CAP = 5.0
RECRUITING_CAP = 2.0


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
    """Convert a value safely to float."""

    if value is None:
        return 0.0

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return 0.0


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

    x_mean = (
        sum(x_values)
        / len(x_values)
    )

    y_mean = (
        sum(y_values)
        / len(y_values)
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

    return numerator / denominator


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
                predicted
                -
                actual
            )
            for predicted, actual in zip(
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
                predicted
                -
                actual
            )
            ** 2
            for predicted, actual in zip(
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


def get_returning_percent(record):
    """Read overall returning production percentage."""

    if not record:
        return 0.0

    overall = record.get(
        "overall",
        {}
    )

    return safe_float(
        overall.get(
            "percent"
        )
    )


def build_analysis_records():
    """Build one historical analysis record per team."""

    ratings_2024 = load_json(
        RATINGS_2024_FILE
    )

    ratings_2025 = load_json(
        RATINGS_2025_FILE
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

    draft_losses = []

    if DRAFT_FILE.exists():
        draft_losses = load_json(
            DRAFT_FILE
        )

    ratings_2024_lookup = build_lookup(
        ratings_2024
    )

    ratings_2025_lookup = build_lookup(
        ratings_2025
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

    draft_lookup = build_lookup(
        draft_losses
    )

    teams = []

    for team_name in sorted(
        ratings_2024_lookup
    ):

        if team_name not in ratings_2025_lookup:
            continue

        rating_2024 = safe_float(
            ratings_2024_lookup[
                team_name
            ].get(
                "power_rating"
            )
        )

        rating_2025 = safe_float(
            ratings_2025_lookup[
                team_name
            ].get(
                "power_rating"
            )
        )

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

        draft_record = draft_lookup.get(
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

        teams.append(
            {
                "team":
                    team_name,

                "rating_2024":
                    rating_2024,

                "rating_2025":
                    rating_2025,

                "rating_change":
                    rating_2025
                    -
                    rating_2024,

                "returning_percent":
                    get_returning_percent(
                        returning_record
                    ),

                "incoming_high_end":
                    safe_float(
                        incoming.get(
                            "high_end_count"
                        )
                    ),

                "outgoing_high_end":
                    safe_float(
                        outgoing.get(
                            "high_end_count"
                        )
                    ),

                "four_star_count":
                    safe_float(
                        recruiting_record.get(
                            "four_star_count"
                        )
                    ),

                "top_10_recruiting":
                    safe_float(
                        recruiting_record.get(
                            "top_10_average_rating"
                        )
                    ),

                "drafted_count":
                    safe_float(
                        draft_record.get(
                            "drafted_count"
                        )
                    ),

                "draft_capital":
                    safe_float(
                        draft_record.get(
                            "draft_capital"
                        )
                    ),
            }
        )

    return teams


def calculate_context(teams):
    """Calculate population context for centered metrics."""

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


def returning_adjustment(
    team,
    context,
    max_points
):
    """
    Center returning production around the national average.

    One standard deviation above or below average receives
    roughly +/- max_points before the cap.
    """

    if max_points == 0:
        return 0.0

    std = context[
        "returning_std"
    ]

    if std == 0:
        return 0.0

    z_score = (
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
        z_score
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
    """
    Incoming 0.90+ transfers create a positive bonus.

    Zero elite incoming transfers = zero bonus.
    """

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
    """
    Outgoing 0.90+ transfers create a negative adjustment.
    """

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
    """
    Recruiting provides only a small positive bonus.

    The worst class gets approximately zero.
    The strongest class can receive up to max_points.

    Recruiting never creates a negative adjustment.
    """

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
    """Generate one preseason projection."""

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

    projected_rating = (
        team[
            "rating_2024"
        ]
        +
        total_adjustment
    )

    return {
        "projected_rating":
            projected_rating,

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
    """Evaluate one parameter combination."""

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
                "rating_2025"
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
    """Search all parameter combinations."""

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


def model_is_better(
    result,
    baseline_correlation,
    baseline_mae,
    baseline_rmse
):
    """
    Require improvement in all three major validation metrics.
    """

    if result[
        "correlation"
    ] is None:
        return False

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
    """
    Rank valid models using all three metrics.

    Correlation receives substantial importance, but MAE and
    RMSE improvements must also contribute.
    """

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
    """Build final team-level validation output."""

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
            "rating_2025"
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
    """Run Version 2 combined preseason validation."""

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
        team[
            "rating_2024"
        ]
        for team in teams
    ]

    actuals = [
        team[
            "rating_2025"
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
        "PROJECT GRIDIRON PRESEASON MODEL V2"
    )

    print("=" * 72)

    print(
        f"Teams tested: "
        f"{len(teams)}"
    )

    print()

    print(
        "BASELINE PERFORMANCE"
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
        "SCALING RULES"
    )

    print("-" * 72)

    print(
        "Returning production: "
        "centered around national average"
    )

    print(
        "Incoming elite transfers: "
        "positive bonus only"
    )

    print(
        "Outgoing elite transfers: "
        "negative penalty only"
    )

    print(
        "Recruiting: "
        "small positive bonus only"
    )

    print()

    results = run_search(
        teams,
        context
    )

    valid_models = [
        result
        for result in results
        if model_is_better(
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
        f"Models improving all three metrics: "
        f"{len(valid_models)}"
    )

    print()

    if not valid_models:

        print(
            "RESULT: No tested combined model "
            "improved correlation, MAE, and RMSE simultaneously."
        )

        print()

        print(
            "Best models by MAE:"
        )

        print("-" * 72)

        by_mae = sorted(
            results,
            key=lambda result:
                result[
                    "mae"
                ]
        )

        for result in by_mae[:10]:

            print(
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

        return

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

    print(
        "BEST VALID MODEL"
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
        f"Baseline correlation: "
        f"{baseline_correlation:.4f}"
    )

    print(
        f"Model correlation: "
        f"{best['correlation']:.4f}"
    )

    print(
        f"Correlation improvement: "
        f"{best['correlation'] - baseline_correlation:+.4f}"
    )

    print()

    print(
        f"Baseline MAE: "
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
        f"Baseline RMSE: "
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
        "TOP 10 VALID MODELS"
    )

    print("-" * 72)

    for rank, result in enumerate(
        valid_models[:10],
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
        "BIGGEST POSITIVE ADJUSTMENTS"
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
            f"{team['rating_2024']:.2f} -> "
            f"{team['projected_rating']:.2f} "
            f"({team['total_adjustment']:+.2f}), "
            f"actual="
            f"{team['rating_2025']:.2f}"
        )

    print()

    print(
        "BIGGEST NEGATIVE ADJUSTMENTS"
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
            f"{team['rating_2024']:.2f} -> "
            f"{team['projected_rating']:.2f} "
            f"({team['total_adjustment']:+.2f}), "
            f"actual="
            f"{team['rating_2025']:.2f}"
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
            f"projected="
            f"{team['projected_rating']:.2f}, "
            f"actual="
            f"{team['rating_2025']:.2f}, "
            f"error="
            f"{team['projection_error']:+.2f}, "
            f"adjustment="
            f"{team['total_adjustment']:+.2f}"
        )

    output = {
        "season":
            2025,

        "version":
            2,

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
