"""
Project Gridiron
Coaching Continuity Validation V2

Historical experiment:

    2024 coaching context
        +
    preseason 2025 coaching situation
        ->
    2025 Project Gridiron rating

This validator tests whether coaching information adds predictive
value beyond the 2024 SP+ baseline.

Candidate coaching signals include:

- Same head coach
- New head coach
- First-year coach
- Second-year coach
- Tenure
- Established coach
- Long-tenure coach

Contextual coaching-change signals:

- Change after bad prior SP+
- Change after good prior SP+
- Change after losing season
- Change after winning season
- Change x prior SP+
- Change x prior SRS
- Change x prior win percentage
- Change x prior point differential

A coaching adjustment is considered valid only if it improves:
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


COACHING_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "coaching_continuity_v2_2025.json"
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
    / "coaching_continuity_validation_v2_2025.json"
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

    if isinstance(
        value,
        bool
    ):
        return (
            1.0
            if value
            else 0.0
        )

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

    coaching_records = load_json(
        COACHING_FILE
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

    coaching_lookup = build_lookup(
        coaching_records
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

        if team_name not in coaching_lookup:
            continue

        coaching = coaching_lookup[
            team_name
        ]

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

        same_head_coach = safe_float(
            coaching.get(
                "same_head_coach"
            )
        )

        new_head_coach = safe_float(
            coaching.get(
                "new_head_coach"
            )
        )

        first_year = safe_float(
            coaching.get(
                "first_year_current_program"
            )
        )

        second_year = safe_float(
            coaching.get(
                "second_year_current_program"
            )
        )

        tenure_years = safe_float(
            coaching.get(
                "tenure_years"
            )
        )

        established = safe_float(
            coaching.get(
                "established_coach"
            )
        )

        long_tenure = safe_float(
            coaching.get(
                "long_tenure"
            )
        )

        prior_win_pct = safe_float(
            coaching.get(
                "prior_coach_win_percentage"
            )
        )

        prior_srs = safe_float(
            coaching.get(
                "prior_coach_srs"
            )
        )

        prior_sp = safe_float(
            coaching.get(
                "prior_coach_sp_overall"
            )
        )

        prior_point_diff = safe_float(
            coaching.get(
                "prior_coach_point_differential"
            )
        )

        change_after_bad_sp = safe_float(
            coaching.get(
                "change_after_bad_sp"
            )
        )

        change_after_good_sp = safe_float(
            coaching.get(
                "change_after_good_sp"
            )
        )

        change_after_losing = safe_float(
            coaching.get(
                "change_after_losing_season"
            )
        )

        change_after_winning = safe_float(
            coaching.get(
                "change_after_winning_season"
            )
        )

        change_x_prior_sp = safe_float(
            coaching.get(
                "change_x_prior_sp"
            )
        )

        change_x_prior_srs = safe_float(
            coaching.get(
                "change_x_prior_srs"
            )
        )

        change_x_prior_win_pct = safe_float(
            coaching.get(
                "change_x_prior_win_pct"
            )
        )

        change_x_prior_point_diff = safe_float(
            coaching.get(
                "change_x_prior_point_diff"
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

                "same_head_coach":
                    same_head_coach,

                "new_head_coach":
                    new_head_coach,

                "first_year":
                    first_year,

                "second_year":
                    second_year,

                "tenure_years":
                    tenure_years,

                "established_coach":
                    established,

                "long_tenure":
                    long_tenure,

                "prior_win_pct":
                    prior_win_pct,

                "prior_srs":
                    prior_srs,

                "prior_sp":
                    prior_sp,

                "prior_point_diff":
                    prior_point_diff,

                "change_after_bad_sp":
                    change_after_bad_sp,

                "change_after_good_sp":
                    change_after_good_sp,

                "change_after_losing":
                    change_after_losing,

                "change_after_winning":
                    change_after_winning,

                "change_x_prior_sp":
                    change_x_prior_sp,

                "change_x_prior_srs":
                    change_x_prior_srs,

                "change_x_prior_win_pct":
                    change_x_prior_win_pct,

                "change_x_prior_point_diff":
                    change_x_prior_point_diff,
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


def metric_correlation(
    teams,
    metric_key
):
    """Correlation between coaching metric and rating change."""

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
    """Add standardized coaching adjustment to SP+ baseline."""

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
    """Run coaching continuity validation."""

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
            "same_head_coach",
            "Same head coach"
        ),
        (
            "new_head_coach",
            "New head coach"
        ),
        (
            "first_year",
            "First-year coach"
        ),
        (
            "second_year",
            "Second-year coach"
        ),
        (
            "tenure_years",
            "Head-coach tenure"
        ),
        (
            "established_coach",
            "Established coach"
        ),
        (
            "long_tenure",
            "Long-tenure coach"
        ),
        (
            "change_after_bad_sp",
            "Coaching change after SP+ below -10"
        ),
        (
            "change_after_good_sp",
            "Coaching change after SP+ above +10"
        ),
        (
            "change_after_losing",
            "Coaching change after losing season"
        ),
        (
            "change_after_winning",
            "Coaching change after winning season"
        ),
        (
            "change_x_prior_sp",
            "Coaching change x prior SP+"
        ),
        (
            "change_x_prior_srs",
            "Coaching change x prior SRS"
        ),
        (
            "change_x_prior_win_pct",
            "Coaching change x prior win percentage"
        ),
        (
            "change_x_prior_point_diff",
            "Coaching change x prior point differential"
        ),
    ]

    print("=" * 76)

    print(
        "COACHING CONTINUITY V2 VALIDATION"
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
        "COACHING METRICS VS 2024 -> 2025 RATING CHANGE"
    )

    print("-" * 76)

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
        "STRONGEST COACHING SIGNALS"
    )

    print("-" * 76)

    for result in metric_results[:12]:

        print(
            f"{result['label']}: "
            f"{result['correlation']:+.4f}"
        )

    print()

    print(
        "SP+ + COACHING ADJUSTMENT TESTS"
    )

    print("-" * 76)

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
        "TOP 20 VALID COACHING MODELS"
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
        "BEST COACHING MODEL"
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
            f"Coaching model correlation: "
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
            f"Coaching model MAE: "
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
            f"Coaching model RMSE: "
            f"{best['rmse']:.2f}"
        )

        print(
            f"Improvement: "
            f"{baseline_rmse - best['rmse']:+.2f}"
        )

    else:

        best = None

        print(
            "No tested coaching adjustment improved "
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
