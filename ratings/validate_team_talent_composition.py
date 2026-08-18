"""
Project Gridiron
Team Talent Composition Validation

Historical experiment:

    2024 roster talent composition
        ->
    2025 Project Gridiron rating

This validator tests whether roster talent adds predictive value
beyond the 2024 SP+ baseline.

It evaluates both:

1. Absolute 2025 rating relationships
2. 2024 -> 2025 rating-change relationships

Candidate metrics include:

- Average roster rating
- Median roster rating
- Top-10 average roster rating
- Top-20 average roster rating
- Top-30 average roster rating
- Blue-chip percentage
- Elite percentage
- Blue-chip count
- Elite count
- Five-star count
- Four-star count
- Position-group average talent:
    QB
    SKILL
    OL
    DL
    LB
    DB

It also tests rating coverage explicitly so we can detect whether
missing recruiting matches are creating misleading signals.

A model is considered valid only if it improves:
    correlation
    MAE
    RMSE

versus SP+ alone.

This module does NOT modify production ratings.
"""

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


TALENT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "team_talent_composition_2024.json"
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
    / "team_talent_composition_validation_2025.json"
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

    return sum(values) / len(values)


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
    """Standardize value."""

    if std == 0:
        return 0.0

    return (
        value
        -
        average
    ) / std


def build_records():
    """Build matching FBS historical records."""

    talent_records = load_json(
        TALENT_FILE
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

    talent_lookup = build_lookup(
        talent_records
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

        if team_name not in talent_lookup:
            continue

        talent = talent_lookup[
            team_name
        ]

        position_groups = talent.get(
            "position_groups",
            {}
        )

        def position_average(group):
            return safe_float(
                position_groups.get(
                    group,
                    {}
                ).get(
                    "average_rating"
                )
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

                "rating_coverage":
                    safe_float(
                        talent.get(
                            "rating_coverage"
                        )
                    ),

                "average_rating":
                    safe_float(
                        talent.get(
                            "average_rating"
                        )
                    ),

                "median_rating":
                    safe_float(
                        talent.get(
                            "median_rating"
                        )
                    ),

                "top_10_average_rating":
                    safe_float(
                        talent.get(
                            "top_10_average_rating"
                        )
                    ),

                "top_20_average_rating":
                    safe_float(
                        talent.get(
                            "top_20_average_rating"
                        )
                    ),

                "top_30_average_rating":
                    safe_float(
                        talent.get(
                            "top_30_average_rating"
                        )
                    ),

                "blue_chip_percentage":
                    safe_float(
                        talent.get(
                            "blue_chip_percentage"
                        )
                    ),

                "elite_percentage":
                    safe_float(
                        talent.get(
                            "elite_percentage"
                        )
                    ),

                "blue_chip_count":
                    safe_float(
                        talent.get(
                            "blue_chip_count"
                        )
                    ),

                "elite_count":
                    safe_float(
                        talent.get(
                            "elite_count"
                        )
                    ),

                "five_star_count":
                    safe_float(
                        talent.get(
                            "five_star_count"
                        )
                    ),

                "four_star_count":
                    safe_float(
                        talent.get(
                            "four_star_count"
                        )
                    ),

                "qb_average_rating":
                    position_average(
                        "QB"
                    ),

                "skill_average_rating":
                    position_average(
                        "SKILL"
                    ),

                "ol_average_rating":
                    position_average(
                        "OL"
                    ),

                "dl_average_rating":
                    position_average(
                        "DL"
                    ),

                "lb_average_rating":
                    position_average(
                        "LB"
                    ),

                "db_average_rating":
                    position_average(
                        "DB"
                    ),
            }
        )

    return teams


def calculate_sp_context(teams):
    """Calculate SP+ mapping context."""

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
    """Map SP+ to Project Gridiron scale."""

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


def correlation_to_target(
    teams,
    metric_key,
    target_key
):
    """Correlation between talent metric and target."""

    x_values = [
        team[
            metric_key
        ]
        for team in teams
    ]

    y_values = [
        team[
            target_key
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
    """Add standardized talent adjustment to SP+ baseline."""

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
    """Run team talent validation."""

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
            "rating_coverage",
            "Recruiting-rating coverage"
        ),
        (
            "average_rating",
            "Average roster rating"
        ),
        (
            "median_rating",
            "Median roster rating"
        ),
        (
            "top_10_average_rating",
            "Top-10 roster rating"
        ),
        (
            "top_20_average_rating",
            "Top-20 roster rating"
        ),
        (
            "top_30_average_rating",
            "Top-30 roster rating"
        ),
        (
            "blue_chip_percentage",
            "Blue-chip percentage"
        ),
        (
            "elite_percentage",
            "Elite-player percentage"
        ),
        (
            "blue_chip_count",
            "Blue-chip count"
        ),
        (
            "elite_count",
            "Elite-player count"
        ),
        (
            "five_star_count",
            "Five-star count"
        ),
        (
            "four_star_count",
            "Four-star count"
        ),
        (
            "qb_average_rating",
            "QB average talent"
        ),
        (
            "skill_average_rating",
            "Skill-position average talent"
        ),
        (
            "ol_average_rating",
            "OL average talent"
        ),
        (
            "dl_average_rating",
            "DL average talent"
        ),
        (
            "lb_average_rating",
            "LB average talent"
        ),
        (
            "db_average_rating",
            "DB average talent"
        ),
    ]

    print("=" * 76)

    print(
        "TEAM TALENT COMPOSITION VALIDATION"
    )

    print("=" * 76)

    print(
        f"Teams tested: "
        f"{len(teams)}"
    )

    print()

    print(
        "SP+ BASELINE"
    )

    print("-" * 76)

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
        "TALENT METRICS VS ABSOLUTE 2025 RATING"
    )

    print("-" * 76)

    absolute_results = []

    for (
        key,
        label
    ) in metrics:

        correlation = (
            correlation_to_target(
                teams,
                key,
                "actual_2025"
            )
        )

        absolute_results.append(
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

    print()

    print(
        "TALENT METRICS VS 2024 -> 2025 RATING CHANGE"
    )

    print("-" * 76)

    change_results = []

    for (
        key,
        label
    ) in metrics:

        correlation = (
            correlation_to_target(
                teams,
                key,
                "rating_change"
            )
        )

        change_results.append(
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

    absolute_results.sort(
        key=lambda result:
            abs(
                result[
                    "correlation"
                ]
            ),
        reverse=True,
    )

    change_results.sort(
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
        "STRONGEST ABSOLUTE TALENT SIGNALS"
    )

    print("-" * 76)

    for result in absolute_results[:10]:

        print(
            f"{result['label']}: "
            f"{result['correlation']:+.4f}"
        )

    print()

    print(
        "STRONGEST YEAR-OVER-YEAR TALENT SIGNALS"
    )

    print("-" * 76)

    for result in change_results[:10]:

        print(
            f"{result['label']}: "
            f"{result['correlation']:+.4f}"
        )

    print()

    print(
        "SP+ + TEAM TALENT ADJUSTMENT TESTS"
    )

    print("-" * 76)

    model_results = []

    for metric in absolute_results:

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
        "TOP 20 VALID TEAM TALENT MODELS"
    )

    print("-" * 76)

    for rank, result in enumerate(
        valid_models[:20],
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
        "BEST TEAM TALENT MODEL"
    )

    print("-" * 76)

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
            f"Model correlation: "
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
            f"Model MAE: "
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
            f"Model RMSE: "
            f"{best['rmse']:.2f}"
        )

        print(
            f"Improvement: "
            f"{baseline_rmse - best['rmse']:+.2f}"
        )

    else:

        best = None

        print(
            "No tested roster-talent adjustment improved "
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

        "absolute_correlations":
            absolute_results,

        "change_correlations":
            change_results,

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
