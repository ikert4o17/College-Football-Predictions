"""
Project Gridiron
QB Continuity Validation

Historical experiment:

    2024 QB situation
        ->
    2025 team performance

This validator tests whether quarterback continuity adds predictive
value beyond the 2024 SP+ baseline.

Candidate QB signals include:

- Primary QB returned
- Primary QB transferred
- Primary QB left roster
- Primary pass usage
- Primary average passing PPA
- Primary total passing PPA
- Returning QB usage
- Lost QB usage
- Returning QB quality
- Lost QB quality
- Continuity score
- Primary / secondary usage gap
- Usage-weighted returning QB value
- Usage-weighted lost QB value

A QB adjustment is only considered useful if it improves:
    correlation
    MAE
    RMSE

This module does NOT modify production ratings.
"""

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


QB_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "qb_continuity_2025.json"
)

SP_2024_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "sp_ratings"
    / "2024.json"
)

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

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "qb_continuity_validation_2025.json"
)


ADJUSTMENT_WEIGHTS = [
    0.25,
    0.50,
    0.75,
    1.00,
    1.25,
    1.50,
    2.00,
    2.50,
    3.00,
]


def load_json(path):
    """Load JSON."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def build_lookup(records):
    """Build team lookup."""

    return {
        record["team"]: record
        for record in records
        if record.get("team")
    }


def safe_float(value):
    """Safely convert value to float."""

    if value is None:
        return 0.0

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return 0.0


def mean(values):
    """Arithmetic mean."""

    if not values:
        return 0.0

    return (
        sum(values)
        /
        len(values)
    )


def standard_deviation(values):
    """Population standard deviation."""

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


def z_score(
    value,
    average,
    std
):
    """Standardize a value."""

    if std == 0:
        return 0.0

    return (
        value
        -
        average
    ) / std


def build_records():
    """Build matching FBS historical records."""

    qb_records = load_json(
        QB_FILE
    )

    sp_2024 = load_json(
        SP_2024_FILE
    )

    gridiron_2024 = load_json(
        GRIDIRON_2024_FILE
    )

    gridiron_2025 = load_json(
        GRIDIRON_2025_FILE
    )

    qb_lookup = build_lookup(
        qb_records
    )

    sp_lookup = build_lookup(
        sp_2024
    )

    gridiron_2024_lookup = build_lookup(
        gridiron_2024
    )

    gridiron_2025_lookup = build_lookup(
        gridiron_2025
    )

    teams = []

    for team_name in sorted(
        gridiron_2024_lookup
    ):

        if team_name not in gridiron_2025_lookup:
            continue

        if team_name not in sp_lookup:
            continue

        qb = qb_lookup.get(
            team_name,
            {}
        )

        sp_rating = safe_float(
            sp_lookup[
                team_name
            ].get(
                "rating"
            )
        )

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

        primary_returned = (
            1.0
            if qb.get(
                "primary_returned"
            )
            else 0.0
        )

        primary_transferred = (
            1.0
            if qb.get(
                "primary_transferred"
            )
            else 0.0
        )

        primary_left_roster = (
            1.0
            if qb.get(
                "primary_left_roster"
            )
            else 0.0
        )

        primary_usage = safe_float(
            qb.get(
                "primary_pass_usage"
            )
        )

        primary_avg_ppa = safe_float(
            qb.get(
                "primary_average_pass_ppa"
            )
        )

        primary_total_ppa = safe_float(
            qb.get(
                "primary_total_pass_ppa"
            )
        )

        returning_usage = safe_float(
            qb.get(
                "returning_primary_usage"
            )
        )

        lost_usage = safe_float(
            qb.get(
                "lost_primary_usage"
            )
        )

        returning_quality = safe_float(
            qb.get(
                "returning_primary_quality"
            )
        )

        lost_quality = safe_float(
            qb.get(
                "lost_primary_quality"
            )
        )

        continuity_score = safe_float(
            qb.get(
                "continuity_score"
            )
        )

        usage_gap = safe_float(
            qb.get(
                "primary_secondary_usage_gap"
            )
        )

        returning_value = (
            returning_usage
            *
            returning_quality
        )

        lost_value = (
            lost_usage
            *
            lost_quality
        )

        signed_qb_value = (
            returning_value
            -
            lost_value
        )

        teams.append(
            {
                "team":
                    team_name,

                "sp_2024":
                    sp_rating,

                "gridiron_2024":
                    gridiron_2024_rating,

                "actual_2025":
                    gridiron_2025_rating,

                "rating_change":
                    gridiron_2025_rating
                    -
                    gridiron_2024_rating,

                "primary_returned":
                    primary_returned,

                "primary_transferred":
                    primary_transferred,

                "primary_left_roster":
                    primary_left_roster,

                "primary_usage":
                    primary_usage,

                "primary_avg_ppa":
                    primary_avg_ppa,

                "primary_total_ppa":
                    primary_total_ppa,

                "returning_usage":
                    returning_usage,

                "lost_usage":
                    lost_usage,

                "returning_quality":
                    returning_quality,

                "lost_quality":
                    lost_quality,

                "continuity_score":
                    continuity_score,

                "usage_gap":
                    usage_gap,

                "returning_value":
                    returning_value,

                "lost_value":
                    lost_value,

                "signed_qb_value":
                    signed_qb_value,
            }
        )

    return teams


def calculate_sp_context(teams):
    """Calculate mapping context from SP+ to Gridiron scale."""

    sp_values = [
        team[
            "sp_2024"
        ]
        for team in teams
    ]

    gridiron_values = [
        team[
            "gridiron_2024"
        ]
        for team in teams
    ]

    return {
        "sp_mean":
            mean(
                sp_values
            ),

        "sp_std":
            standard_deviation(
                sp_values
            ),

        "gridiron_mean":
            mean(
                gridiron_values
            ),

        "gridiron_std":
            standard_deviation(
                gridiron_values
            ),
    }


def map_sp_to_gridiron(
    team,
    context
):
    """Map SP+ onto Project Gridiron scale."""

    standardized = z_score(
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
        standardized
        *
        context[
            "gridiron_std"
        ]
    )


def metric_correlation(
    teams,
    metric_key
):
    """Correlation between QB metric and rating change."""

    x_values = [
        team[
            metric_key
        ]
        for team in teams
    ]

    y_values = [
        team[
            "rating_change"
        ]
        for team in teams
    ]

    return pearson_correlation(
        x_values,
        y_values
    )


def evaluate_adjustment(
    teams,
    context,
    metric_key,
    points_per_std
):
    """
    Add a standardized QB metric adjustment to SP+ baseline.
    """

    metric_values = [
        team[
            metric_key
        ]
        for team in teams
    ]

    metric_mean = mean(
        metric_values
    )

    metric_std = standard_deviation(
        metric_values
    )

    predictions = []

    actuals = []

    for team in teams:

        baseline = map_sp_to_gridiron(
            team,
            context
        )

        metric_z = z_score(
            team[
                metric_key
            ],
            metric_mean,
            metric_std
        )

        adjustment = (
            metric_z
            *
            points_per_std
        )

        # Keep QB adjustment sane.
        adjustment = max(
            -4.0,
            min(
                adjustment,
                4.0
            )
        )

        prediction = (
            baseline
            +
            adjustment
        )

        predictions.append(
            prediction
        )

        actuals.append(
            team[
                "actual_2025"
            ]
        )

    return {
        "metric":
            metric_key,

        "points_per_std":
            points_per_std,

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


def analyze():
    """Run QB continuity validation."""

    teams = build_records()

    if not teams:

        print(
            "No matching teams found."
        )
        return

    context = calculate_sp_context(
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

    metrics = [
        (
            "primary_returned",
            "Primary QB returned"
        ),
        (
            "primary_transferred",
            "Primary QB transferred"
        ),
        (
            "primary_left_roster",
            "Primary QB left roster"
        ),
        (
            "primary_usage",
            "Primary QB pass usage"
        ),
        (
            "primary_avg_ppa",
            "Primary QB average pass PPA"
        ),
        (
            "primary_total_ppa",
            "Primary QB total pass PPA"
        ),
        (
            "returning_usage",
            "Returning primary QB usage"
        ),
        (
            "lost_usage",
            "Lost primary QB usage"
        ),
        (
            "returning_quality",
            "Returning primary QB quality"
        ),
        (
            "lost_quality",
            "Lost primary QB quality"
        ),
        (
            "continuity_score",
            "QB continuity score"
        ),
        (
            "usage_gap",
            "Primary-secondary usage gap"
        ),
        (
            "returning_value",
            "Usage-weighted returning QB value"
        ),
        (
            "lost_value",
            "Usage-weighted lost QB value"
        ),
        (
            "signed_qb_value",
            "Net usage-weighted QB value"
        ),
    ]

    print("=" * 72)

    print(
        "QB CONTINUITY VALIDATION"
    )

    print("=" * 72)

    print(
        f"Teams tested: "
        f"{len(teams)}"
    )

    print()

    print(
        "SP+ BASELINE"
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
        "QB METRICS VS 2024 -> 2025 RATING CHANGE"
    )

    print("-" * 72)

    metric_results = []

    for (
        key,
        label
    ) in metrics:

        correlation = metric_correlation(
            teams,
            key
        )

        metric_results.append(
            {
                "key":
                    key,

                "label":
                    label,

                "correlation":
                    correlation,
            }
        )

        print(
            f"{label}: "
            f"{correlation:+.4f}"
        )

    metric_results.sort(
        key=lambda result:
            abs(
                result[
                    "correlation"
                ]
            ),
        reverse=True,
    )

    print()

    print(
        "STRONGEST QB SIGNALS"
    )

    print("-" * 72)

    for result in metric_results[:10]:

        print(
            f"{result['label']}: "
            f"{result['correlation']:+.4f}"
        )

    print()

    print(
        "SP+ + QB ADJUSTMENT TESTS"
    )

    print("-" * 72)

    model_results = []

    for metric in metric_results:

        for weight in ADJUSTMENT_WEIGHTS:

            result = evaluate_adjustment(
                teams,
                context,
                metric[
                    "key"
                ],
                weight
            )

            result[
                "label"
            ] = metric[
                "label"
            ]

            result[
                "improves_all"
            ] = (
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

            model_results.append(
                result
            )

    valid_models = [
        result
        for result in model_results
        if result[
            "improves_all"
        ]
    ]

    for result in valid_models:

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
            "score"
        ] = (
            correlation_gain
            *
            100.0
            +
            mae_gain
            +
            rmse_gain
        )

    valid_models.sort(
        key=lambda result:
            result[
                "score"
            ],
        reverse=True,
    )

    print(
        f"Models improving all three metrics: "
        f"{len(valid_models)}"
    )

    print()

    print(
        "TOP 15 VALID QB MODELS"
    )

    print("-" * 72)

    for rank, result in enumerate(
        valid_models[:15],
        start=1
    ):

        print(
            f"{rank}. "
            f"{result['label']} "
            f"@ {result['points_per_std']:.2f} pts/std: "
            f"corr="
            f"{result['correlation']:.4f}, "
            f"MAE="
            f"{result['mae']:.2f}, "
            f"RMSE="
            f"{result['rmse']:.2f}"
        )

    print()

    print(
        "BEST QB MODEL"
    )

    print("-" * 72)

    if valid_models:

        best = valid_models[0]

        print(
            f"Metric: "
            f"{best['label']}"
        )

        print(
            f"Adjustment: "
            f"{best['points_per_std']:.2f} points/std"
        )

        print()

        print(
            f"SP+ correlation: "
            f"{baseline_correlation:.4f}"
        )

        print(
            f"QB model correlation: "
            f"{best['correlation']:.4f}"
        )

        print(
            f"Change: "
            f"{best['correlation'] - baseline_correlation:+.4f}"
        )

        print()

        print(
            f"SP+ MAE: "
            f"{baseline_mae:.2f}"
        )

        print(
            f"QB model MAE: "
            f"{best['mae']:.2f}"
        )

        print(
            f"Improvement: "
            f"{baseline_mae - best['mae']:+.2f}"
        )

        print()

        print(
            f"SP+ RMSE: "
            f"{baseline_rmse:.2f}"
        )

        print(
            f"QB model RMSE: "
            f"{best['rmse']:.2f}"
        )

        print(
            f"Improvement: "
            f"{baseline_rmse - best['rmse']:+.2f}"
        )

    else:

        best = None

        print(
            "No tested QB continuity adjustment improved "
            "correlation, MAE, and RMSE simultaneously."
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

        "metric_correlations":
            metric_results,

        "valid_models":
            valid_models,

        "best_model":
            best,
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
