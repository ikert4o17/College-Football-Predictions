"""
Project Gridiron
Transfer Production + Experience Validation V2

Historical experiment:

    2024 player production
        +
    2025 transfer movement
        ->
    2025 Project Gridiron rating

This validator tests whether transfer production adds predictive
value beyond the 2024 SP+ baseline.

It focuses only on position groups where CFBD production metrics
are interpretable:

    QB
    RB / WR / TE

Candidate signals include:

QB:
    incoming pass PPA
    outgoing pass PPA
    net pass PPA
    incoming pass usage
    outgoing pass usage
    net pass usage
    incoming QB talent-production score
    outgoing QB talent-production score
    net QB talent-production score

Skill:
    incoming total PPA
    outgoing total PPA
    net total PPA
    incoming usage
    outgoing usage
    net usage
    incoming skill talent-production score
    outgoing skill talent-production score
    net skill talent-production score

Combined:
    QB + skill PPA
    QB + skill usage
    QB + skill talent-production score

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


TRANSFER_PRODUCTION_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "transfer_production_v2_2025.json"
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
    / "transfer_production_validation_v2_2025.json"
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

    transfer_records = load_json(
        TRANSFER_PRODUCTION_FILE
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

    transfer_lookup = build_lookup(
        transfer_records
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

        transfer = transfer_lookup.get(
            team_name,
            {}
        )

        incoming = transfer.get(
            "incoming",
            {}
        )

        outgoing = transfer.get(
            "outgoing",
            {}
        )

        net = transfer.get(
            "net",
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

        incoming_qb_ppa = safe_float(
            incoming.get(
                "qb_total_pass_ppa_sum"
            )
        )

        outgoing_qb_ppa = safe_float(
            outgoing.get(
                "qb_total_pass_ppa_sum"
            )
        )

        incoming_qb_usage = safe_float(
            incoming.get(
                "qb_pass_usage_sum"
            )
        )

        outgoing_qb_usage = safe_float(
            outgoing.get(
                "qb_pass_usage_sum"
            )
        )

        incoming_qb_score = safe_float(
            incoming.get(
                "qb_talent_production_score"
            )
        )

        outgoing_qb_score = safe_float(
            outgoing.get(
                "qb_talent_production_score"
            )
        )

        incoming_skill_ppa = safe_float(
            incoming.get(
                "skill_total_ppa_sum"
            )
        )

        outgoing_skill_ppa = safe_float(
            outgoing.get(
                "skill_total_ppa_sum"
            )
        )

        incoming_skill_usage = safe_float(
            incoming.get(
                "skill_usage_sum"
            )
        )

        outgoing_skill_usage = safe_float(
            outgoing.get(
                "skill_usage_sum"
            )
        )

        incoming_skill_score = safe_float(
            incoming.get(
                "skill_talent_production_score"
            )
        )

        outgoing_skill_score = safe_float(
            outgoing.get(
                "skill_talent_production_score"
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

                # QB
                "incoming_qb_ppa":
                    incoming_qb_ppa,

                "outgoing_qb_ppa":
                    outgoing_qb_ppa,

                "net_qb_ppa":
                    incoming_qb_ppa
                    -
                    outgoing_qb_ppa,

                "incoming_qb_usage":
                    incoming_qb_usage,

                "outgoing_qb_usage":
                    outgoing_qb_usage,

                "net_qb_usage":
                    incoming_qb_usage
                    -
                    outgoing_qb_usage,

                "incoming_qb_score":
                    incoming_qb_score,

                "outgoing_qb_score":
                    outgoing_qb_score,

                "net_qb_score":
                    incoming_qb_score
                    -
                    outgoing_qb_score,

                # Skill
                "incoming_skill_ppa":
                    incoming_skill_ppa,

                "outgoing_skill_ppa":
                    outgoing_skill_ppa,

                "net_skill_ppa":
                    incoming_skill_ppa
                    -
                    outgoing_skill_ppa,

                "incoming_skill_usage":
                    incoming_skill_usage,

                "outgoing_skill_usage":
                    outgoing_skill_usage,

                "net_skill_usage":
                    incoming_skill_usage
                    -
                    outgoing_skill_usage,

                "incoming_skill_score":
                    incoming_skill_score,

                "outgoing_skill_score":
                    outgoing_skill_score,

                "net_skill_score":
                    incoming_skill_score
                    -
                    outgoing_skill_score,

                # Combined
                "incoming_total_offensive_ppa":
                    incoming_qb_ppa
                    +
                    incoming_skill_ppa,

                "outgoing_total_offensive_ppa":
                    outgoing_qb_ppa
                    +
                    outgoing_skill_ppa,

                "net_total_offensive_ppa":
                    (
                        incoming_qb_ppa
                        +
                        incoming_skill_ppa
                        -
                        outgoing_qb_ppa
                        -
                        outgoing_skill_ppa
                    ),

                "incoming_total_offensive_usage":
                    incoming_qb_usage
                    +
                    incoming_skill_usage,

                "outgoing_total_offensive_usage":
                    outgoing_qb_usage
                    +
                    outgoing_skill_usage,

                "net_total_offensive_usage":
                    (
                        incoming_qb_usage
                        +
                        incoming_skill_usage
                        -
                        outgoing_qb_usage
                        -
                        outgoing_skill_usage
                    ),

                "incoming_total_offensive_score":
                    incoming_qb_score
                    +
                    incoming_skill_score,

                "outgoing_total_offensive_score":
                    outgoing_qb_score
                    +
                    outgoing_skill_score,

                "net_total_offensive_score":
                    (
                        incoming_qb_score
                        +
                        incoming_skill_score
                        -
                        outgoing_qb_score
                        -
                        outgoing_skill_score
                    ),

                # Direct net values already stored by processor
                "net_productive_qb_count":
                    safe_float(
                        net.get(
                            "productive_qb_count"
                        )
                    ),

                "net_productive_skill_count":
                    safe_float(
                        net.get(
                            "productive_skill_count"
                        )
                    ),
            }
        )

    return teams


def calculate_sp_context(teams):
    """Calculate mapping context."""

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
    """Map SP+ to Gridiron scale."""

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
    """Correlation between transfer metric and rating change."""

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
    """Add standardized transfer adjustment to SP+ baseline."""

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
    """Run transfer production validation."""

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
        # QB
        (
            "incoming_qb_ppa",
            "Incoming QB prior pass PPA"
        ),
        (
            "outgoing_qb_ppa",
            "Outgoing QB prior pass PPA"
        ),
        (
            "net_qb_ppa",
            "Net QB prior pass PPA"
        ),
        (
            "incoming_qb_usage",
            "Incoming QB prior pass usage"
        ),
        (
            "outgoing_qb_usage",
            "Outgoing QB prior pass usage"
        ),
        (
            "net_qb_usage",
            "Net QB prior pass usage"
        ),
        (
            "incoming_qb_score",
            "Incoming QB talent-production score"
        ),
        (
            "outgoing_qb_score",
            "Outgoing QB talent-production score"
        ),
        (
            "net_qb_score",
            "Net QB talent-production score"
        ),

        # Skill
        (
            "incoming_skill_ppa",
            "Incoming skill prior PPA"
        ),
        (
            "outgoing_skill_ppa",
            "Outgoing skill prior PPA"
        ),
        (
            "net_skill_ppa",
            "Net skill prior PPA"
        ),
        (
            "incoming_skill_usage",
            "Incoming skill prior usage"
        ),
        (
            "outgoing_skill_usage",
            "Outgoing skill prior usage"
        ),
        (
            "net_skill_usage",
            "Net skill prior usage"
        ),
        (
            "incoming_skill_score",
            "Incoming skill talent-production score"
        ),
        (
            "outgoing_skill_score",
            "Outgoing skill talent-production score"
        ),
        (
            "net_skill_score",
            "Net skill talent-production score"
        ),

        # Combined
        (
            "incoming_total_offensive_ppa",
            "Incoming offensive transfer prior PPA"
        ),
        (
            "outgoing_total_offensive_ppa",
            "Outgoing offensive transfer prior PPA"
        ),
        (
            "net_total_offensive_ppa",
            "Net offensive transfer prior PPA"
        ),
        (
            "incoming_total_offensive_usage",
            "Incoming offensive transfer prior usage"
        ),
        (
            "outgoing_total_offensive_usage",
            "Outgoing offensive transfer prior usage"
        ),
        (
            "net_total_offensive_usage",
            "Net offensive transfer prior usage"
        ),
        (
            "incoming_total_offensive_score",
            "Incoming offensive talent-production score"
        ),
        (
            "outgoing_total_offensive_score",
            "Outgoing offensive talent-production score"
        ),
        (
            "net_total_offensive_score",
            "Net offensive talent-production score"
        ),
        (
            "net_productive_qb_count",
            "Net productive QB transfer count"
        ),
        (
            "net_productive_skill_count",
            "Net productive skill transfer count"
        ),
    ]

    print("=" * 76)

    print(
        "TRANSFER PRODUCTION + EXPERIENCE V2 VALIDATION"
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
        "TRANSFER PRODUCTION METRICS VS 2024 -> 2025 RATING CHANGE"
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
        "STRONGEST TRANSFER PRODUCTION SIGNALS"
    )

    print("-" * 76)

    for result in metric_results[:15]:

        print(
            f"{result['label']}: "
            f"{result['correlation']:+.4f}"
        )

    print()

    print(
        "SP+ + TRANSFER PRODUCTION ADJUSTMENT TESTS"
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
        "TOP 20 VALID TRANSFER PRODUCTION MODELS"
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
        "BEST TRANSFER PRODUCTION MODEL"
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
            "No tested transfer-production adjustment improved "
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
