"""
Project Gridiron
Combined Preseason Model Validation

Build and validate a combined preseason rating model using:

    Previous-season power rating
    + Returning production
    + Incoming transfer talent
    + Net transfer talent
    + Recruiting talent

NFL Draft losses are retained as a diagnostic variable but are
not forced into the model because standalone validation showed
that they did not improve the baseline.

Historical validation:

    2024 power rating
        ->
    2025 preseason projection
        ->
    Actual 2025 power rating

IMPORTANT:
We currently do not have historical 2025 returning-snaps data.
Therefore snaps are NOT included in this historical validation.

The 2026 production model can later add the manually captured
2026 returning-snaps dataset.

This module does NOT overwrite the production power ratings.
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
    / "preseason_model_validation_2025.json"
)


# ------------------------------------------------------------
# WEIGHT SEARCH
# ------------------------------------------------------------

RETURNING_WEIGHTS = [
    0.00,
    0.01,
    0.02,
    0.03,
    0.05,
    0.075,
    0.10,
]

TRANSFER_WEIGHTS = [
    0.00,
    0.02,
    0.03,
    0.05,
    0.075,
    0.10,
    0.125,
    0.15,
]

NET_TRANSFER_WEIGHTS = [
    0.00,
    0.01,
    0.02,
    0.03,
    0.05,
]

RECRUITING_WEIGHTS = [
    0.00,
    0.01,
    0.02,
    0.03,
    0.05,
]


def load_json(path):
    """Load JSON data."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def build_lookup(records):
    """Build team-name lookup."""

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


def pearson_correlation(
    x_values,
    y_values
):
    """Calculate Pearson correlation."""

    if (
        len(x_values)
        != len(y_values)
    ):
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

    return (
        numerator
        /
        denominator
    )


def mean_absolute_error(
    predictions,
    actuals
):
    """Calculate mean absolute error."""

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
    """Calculate root mean squared error."""

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


def normalize_values(
    teams,
    metric_key
):
    """
    Convert a metric to approximately -1 to +1.

    Centering the variable around the national average means
    average teams receive roughly zero adjustment.
    """

    values = [
        safe_float(
            team.get(
                metric_key
            )
        )
        for team in teams
    ]

    if not values:
        return {}

    minimum = min(
        values
    )

    maximum = max(
        values
    )

    if maximum == minimum:

        return {
            team["team"]: 0.0
            for team in teams
        }

    normalized = {}

    for team in teams:

        value = safe_float(
            team.get(
                metric_key
            )
        )

        zero_to_one = (
            (
                value
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

        normalized[
            team["team"]
        ] = (
            zero_to_one
            *
            2.0
            -
            1.0
        )

    return normalized


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
    """Build one combined historical record per FBS team."""

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

        if (
            team_name
            not in ratings_2025_lookup
        ):
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

        returning_record = (
            returning_lookup.get(
                team_name,
                {}
            )
        )

        transfer_record = (
            transfer_lookup.get(
                team_name,
                {}
            )
        )

        recruiting_record = (
            recruiting_lookup.get(
                team_name,
                {}
            )
        )

        draft_record = (
            draft_lookup.get(
                team_name,
                {}
            )
        )

        incoming = transfer_record.get(
            "incoming",
            {}
        )

        net = transfer_record.get(
            "net",
            {}
        )

        # Previous transfer validation showed that
        # incoming 0.90+ players were the strongest signal.
        incoming_high_end = safe_float(
            incoming.get(
                "high_end_count"
            )
        )

        # Net high-end talent remains available as a smaller
        # secondary transfer signal.
        net_high_end = safe_float(
            net.get(
                "high_end_count"
            )
        )

        # Recruiting validation showed several similar signals.
        # Four-star count produced the strongest tested result,
        # so we use it in this first combined experiment.
        four_star_count = safe_float(
            recruiting_record.get(
                "four_star_count"
            )
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
                    (
                        rating_2025
                        -
                        rating_2024
                    ),

                "returning_percent":
                    get_returning_percent(
                        returning_record
                    ),

                "incoming_high_end":
                    incoming_high_end,

                "net_high_end":
                    net_high_end,

                "four_star_count":
                    four_star_count,

                # Diagnostics only.
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

                "qb_drafted_count":
                    safe_float(
                        draft_record.get(
                            "qb_drafted_count"
                        )
                    ),
            }
        )

    return teams


def build_normalized_metrics(
    teams
):
    """Create normalized versions of model inputs."""

    return {
        "returning":
            normalize_values(
                teams,
                "returning_percent"
            ),

        "incoming_transfer":
            normalize_values(
                teams,
                "incoming_high_end"
            ),

        "net_transfer":
            normalize_values(
                teams,
                "net_high_end"
            ),

        "recruiting":
            normalize_values(
                teams,
                "four_star_count"
            ),
    }


def project_rating(
    team,
    normalized,
    returning_weight,
    transfer_weight,
    net_transfer_weight,
    recruiting_weight
):
    """
    Build one preseason projection.

    We use additive point adjustments rather than replacing
    portions of the baseline rating.

    A weight of 0.10 corresponds to a maximum adjustment
    of roughly +/- 10 rating points for that metric.
    """

    baseline = team[
        "rating_2024"
    ]

    team_name = team[
        "team"
    ]

    returning_adjustment = (
        normalized[
            "returning"
        ][
            team_name
        ]
        *
        returning_weight
        *
        100.0
    )

    transfer_adjustment = (
        normalized[
            "incoming_transfer"
        ][
            team_name
        ]
        *
        transfer_weight
        *
        100.0
    )

    net_transfer_adjustment = (
        normalized[
            "net_transfer"
        ][
            team_name
        ]
        *
        net_transfer_weight
        *
        100.0
    )

    recruiting_adjustment = (
        normalized[
            "recruiting"
        ][
            team_name
        ]
        *
        recruiting_weight
        *
        100.0
    )

    projected = (
        baseline
        +
        returning_adjustment
        +
        transfer_adjustment
        +
        net_transfer_adjustment
        +
        recruiting_adjustment
    )

    return {
        "projected_rating":
            projected,

        "returning_adjustment":
            returning_adjustment,

        "transfer_adjustment":
            transfer_adjustment,

        "net_transfer_adjustment":
            net_transfer_adjustment,

        "recruiting_adjustment":
            recruiting_adjustment,
    }


def evaluate_model(
    teams,
    normalized,
    returning_weight,
    transfer_weight,
    net_transfer_weight,
    recruiting_weight
):
    """Evaluate one combination of model weights."""

    projected = []

    actual = []

    for team in teams:

        result = project_rating(
            team,
            normalized,
            returning_weight,
            transfer_weight,
            net_transfer_weight,
            recruiting_weight
        )

        projected.append(
            result[
                "projected_rating"
            ]
        )

        actual.append(
            team[
                "rating_2025"
            ]
        )

    correlation = pearson_correlation(
        projected,
        actual
    )

    mae = mean_absolute_error(
        projected,
        actual
    )

    rmse = root_mean_squared_error(
        projected,
        actual
    )

    return {
        "returning_weight":
            returning_weight,

        "transfer_weight":
            transfer_weight,

        "net_transfer_weight":
            net_transfer_weight,

        "recruiting_weight":
            recruiting_weight,

        "correlation":
            correlation,

        "mae":
            mae,

        "rmse":
            rmse,
    }


def run_weight_search(
    teams,
    normalized
):
    """Test all configured weight combinations."""

    results = []

    combinations = itertools.product(
        RETURNING_WEIGHTS,
        TRANSFER_WEIGHTS,
        NET_TRANSFER_WEIGHTS,
        RECRUITING_WEIGHTS,
    )

    for (
        returning_weight,
        transfer_weight,
        net_transfer_weight,
        recruiting_weight,
    ) in combinations:

        # Prevent the roster adjustments from overwhelming
        # the historical baseline in this first experiment.
        total_weight = (
            returning_weight
            +
            transfer_weight
            +
            net_transfer_weight
            +
            recruiting_weight
        )

        if total_weight > 0.25:
            continue

        result = evaluate_model(
            teams,
            normalized,
            returning_weight,
            transfer_weight,
            net_transfer_weight,
            recruiting_weight
        )

        results.append(
            result
        )

    return results


def build_final_team_results(
    teams,
    normalized,
    best
):
    """Generate team-level results using the best combination."""

    results = []

    for team in teams:

        projection = project_rating(
            team,
            normalized,
            best[
                "returning_weight"
            ],
            best[
                "transfer_weight"
            ],
            best[
                "net_transfer_weight"
            ],
            best[
                "recruiting_weight"
            ],
        )

        projected_rating = projection[
            "projected_rating"
        ]

        actual_rating = team[
            "rating_2025"
        ]

        results.append(
            {
                **team,

                **projection,

                "projection_error":
                    (
                        projected_rating
                        -
                        actual_rating
                    ),

                "absolute_error":
                    abs(
                        projected_rating
                        -
                        actual_rating
                    ),
            }
        )

    results.sort(
        key=lambda team:
            team[
                "projected_rating"
            ],
        reverse=True,
    )

    return results


def analyze():
    """Run combined preseason model validation."""

    teams = build_analysis_records()

    if not teams:

        print(
            "No matching teams found."
        )

        return

    normalized = build_normalized_metrics(
        teams
    )

    baseline_values = [
        team[
            "rating_2024"
        ]
        for team in teams
    ]

    actual_values = [
        team[
            "rating_2025"
        ]
        for team in teams
    ]

    baseline_correlation = (
        pearson_correlation(
            baseline_values,
            actual_values
        )
    )

    baseline_mae = mean_absolute_error(
        baseline_values,
        actual_values
    )

    baseline_rmse = (
        root_mean_squared_error(
            baseline_values,
            actual_values
        )
    )

    print("=" * 72)

    print(
        "PROJECT GRIDIRON COMBINED PRESEASON MODEL"
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
        f"2024 -> 2025 correlation: "
        f"{baseline_correlation:.4f}"
    )

    print(
        f"Baseline MAE: "
        f"{baseline_mae:.2f}"
    )

    print(
        f"Baseline RMSE: "
        f"{baseline_rmse:.2f}"
    )

    print()

    print(
        "MODEL INPUTS"
    )

    print("-" * 72)

    print(
        "Returning production: "
        "overall returning percentage"
    )

    print(
        "Transfer talent: "
        "incoming 0.90+ transfer count"
    )

    print(
        "Net transfer talent: "
        "incoming minus outgoing 0.90+ count"
    )

    print(
        "Recruiting talent: "
        "four-star recruit count"
    )

    print(
        "NFL Draft losses: "
        "diagnostic only"
    )

    print(
        "Returning snaps: "
        "not available historically for this validation"
    )

    print()

    results = run_weight_search(
        teams,
        normalized
    )

    valid_results = [
        result
        for result in results
        if result[
            "correlation"
        ] is not None
    ]

    # Primary objective:
    # maximize correlation.
    #
    # Tie-breakers:
    # minimize RMSE, then MAE.
    valid_results.sort(
        key=lambda result:
            (
                -result[
                    "correlation"
                ],
                result[
                    "rmse"
                ],
                result[
                    "mae"
                ],
            )
    )

    best = valid_results[0]

    print(
        "BEST COMBINED MODEL"
    )

    print("-" * 72)

    print(
        f"Returning production weight: "
        f"{best['returning_weight'] * 100:.1f}%"
    )

    print(
        f"Incoming transfer weight: "
        f"{best['transfer_weight'] * 100:.1f}%"
    )

    print(
        f"Net transfer weight: "
        f"{best['net_transfer_weight'] * 100:.1f}%"
    )

    print(
        f"Recruiting weight: "
        f"{best['recruiting_weight'] * 100:.1f}%"
    )

    print()

    print(
        f"Baseline correlation: "
        f"{baseline_correlation:.4f}"
    )

    print(
        f"Combined correlation: "
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
        f"Combined MAE: "
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
        f"Combined RMSE: "
        f"{best['rmse']:.2f}"
    )

    print(
        f"RMSE improvement: "
        f"{baseline_rmse - best['rmse']:+.2f}"
    )

    print()

    print(
        "TOP 10 MODEL COMBINATIONS"
    )

    print("-" * 72)

    for rank, result in enumerate(
        valid_results[:10],
        start=1
    ):

        print(
            f"{rank}. "
            f"returning="
            f"{result['returning_weight']:.3f}, "
            f"transfer="
            f"{result['transfer_weight']:.3f}, "
            f"net_transfer="
            f"{result['net_transfer_weight']:.3f}, "
            f"recruiting="
            f"{result['recruiting_weight']:.3f}, "
            f"corr="
            f"{result['correlation']:.4f}, "
            f"MAE="
            f"{result['mae']:.2f}, "
            f"RMSE="
            f"{result['rmse']:.2f}"
        )

    final_team_results = (
        build_final_team_results(
            teams,
            normalized,
            best
        )
    )

    print()

    print(
        "BIGGEST POSITIVE PRESEASON ADJUSTMENTS"
    )

    print("-" * 72)

    positive_adjustments = sorted(
        final_team_results,
        key=lambda team:
            (
                team[
                    "projected_rating"
                ]
                -
                team[
                    "rating_2024"
                ]
            ),
        reverse=True,
    )

    for team in positive_adjustments[:15]:

        adjustment = (
            team[
                "projected_rating"
            ]
            -
            team[
                "rating_2024"
            ]
        )

        print(
            f"{team['team']}: "
            f"{team['rating_2024']:.2f} -> "
            f"{team['projected_rating']:.2f} "
            f"({adjustment:+.2f}), "
            f"actual="
            f"{team['rating_2025']:.2f}"
        )

    print()

    print(
        "BIGGEST NEGATIVE PRESEASON ADJUSTMENTS"
    )

    print("-" * 72)

    negative_adjustments = sorted(
        final_team_results,
        key=lambda team:
            (
                team[
                    "projected_rating"
                ]
                -
                team[
                    "rating_2024"
                ]
            )
    )

    for team in negative_adjustments[:15]:

        adjustment = (
            team[
                "projected_rating"
            ]
            -
            team[
                "rating_2024"
            ]
        )

        print(
            f"{team['team']}: "
            f"{team['rating_2024']:.2f} -> "
            f"{team['projected_rating']:.2f} "
            f"({adjustment:+.2f}), "
            f"actual="
            f"{team['rating_2025']:.2f}"
        )

    print()

    print(
        "LOWEST MODEL ERRORS"
    )

    print("-" * 72)

    best_predictions = sorted(
        final_team_results,
        key=lambda team:
            team[
                "absolute_error"
            ]
    )

    for team in best_predictions[:10]:

        print(
            f"{team['team']}: "
            f"projected="
            f"{team['projected_rating']:.2f}, "
            f"actual="
            f"{team['rating_2025']:.2f}, "
            f"error="
            f"{team['projection_error']:+.2f}"
        )

    print()

    print(
        "LARGEST MODEL ERRORS"
    )

    print("-" * 72)

    worst_predictions = sorted(
        final_team_results,
        key=lambda team:
            team[
                "absolute_error"
            ],
        reverse=True,
    )

    for team in worst_predictions[:15]:

        print(
            f"{team['team']}: "
            f"projected="
            f"{team['projected_rating']:.2f}, "
            f"actual="
            f"{team['rating_2025']:.2f}, "
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

        "best_model":
            best,

        "correlation_improvement":
            (
                best[
                    "correlation"
                ]
                -
                baseline_correlation
            ),

        "mae_improvement":
            (
                baseline_mae
                -
                best[
                    "mae"
                ]
            ),

        "rmse_improvement":
            (
                baseline_rmse
                -
                best[
                    "rmse"
                ]
            ),

        "team_results":
            final_team_results,
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
