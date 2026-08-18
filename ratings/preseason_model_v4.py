"""
Project Gridiron
Combined Preseason Model V4

Purpose
-------
Build and validate a combined preseason model anchored to prior-season SP+.

Unlike earlier experiments that tested one variable family at a time,
V4 forces the validated preseason signals to compete with one another.

Historical validation:

    2024 SP+ baseline
        +
    2025 preseason information
        ->
    2025 Project Gridiron power rating

Candidate feature families:

    Returning production
    Transfer talent
    Transfer production / experience
    QB continuity
    Contextual coaching change

Variables that previously failed to add value beyond SP+ are intentionally
NOT included as direct adjustments:

    Team talent composition
    Recruiting class talent
    NFL draft losses

The goal is NOT to maximize in-sample correlation at any cost.

V4 prefers:
    1. Improvement in correlation
    2. Improvement in MAE
    3. Improvement in RMSE
    4. Smaller / simpler adjustments when performance is similar

Usage:
    python -m ratings.preseason_model_v4

Output:
    data/processed/preseason_model_v4_validation_2025.json

This module does NOT overwrite the 2026 production ratings.
"""

import json
import math
from itertools import product
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# REQUIRED FILES
# ============================================================

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

RETURNING_PRODUCTION_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "returning_production_2025.json"
)

TRANSFER_TALENT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "transfer_talent_2025.json"
)

TRANSFER_PRODUCTION_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "transfer_production_v2_2025.json"
)

QB_CONTINUITY_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "qb_continuity_2025.json"
)

COACHING_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "coaching_continuity_v2_2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "preseason_model_v4_validation_2025.json"
)


# ============================================================
# PARAMETER GRID
# ============================================================

# These are deliberately restrained.
#
# We already know from the individual experiments that giant preseason
# adjustments can improve correlation while destroying calibration.
#
# V4 therefore searches smaller, more realistic ranges.

RETURNING_WEIGHTS = [
    0.00,
    0.25,
    0.50,
    0.75,
    1.00,
]

TRANSFER_TALENT_WEIGHTS = [
    0.00,
    0.25,
    0.50,
    0.75,
    1.00,
]

TRANSFER_PRODUCTION_WEIGHTS = [
    0.00,
    0.25,
    0.50,
    0.75,
    1.00,
    1.25,
    1.50,
]

QB_CONTINUITY_WEIGHTS = [
    0.00,
    0.25,
    0.50,
]

COACHING_WEIGHTS = [
    0.00,
    0.25,
    0.50,
    0.75,
    1.00,
]


# Maximum combined preseason adjustment.

MAX_TOTAL_ADJUSTMENT = 6.0


# ============================================================
# GENERIC HELPERS
# ============================================================

def load_json(path):
    """Load JSON file."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(
            file
        )


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

        return float(
            value
        )

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


def build_lookup(records):
    """Build team lookup."""

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

        if team:

            lookup[
                team
            ] = record

    return lookup


def nested_get(
    record,
    keys,
    default=0.0
):
    """Safely read nested dictionary value."""

    value = record

    for key in keys:

        if not isinstance(
            value,
            dict
        ):

            return default

        value = value.get(
            key
        )

        if value is None:
            return default

    return value


def first_available(
    record,
    candidates,
    default=0.0
):
    """
    Read first available value from candidate key paths.

    Candidate examples:

        ("overall",)
        ("returning_percentage",)
        ("net", "qb_talent_production_score")
    """

    for keys in candidates:

        value = nested_get(
            record,
            keys,
            default=None
        )

        if value is not None:

            return safe_float(
                value
            )

    return safe_float(
        default
    )


# ============================================================
# FILE RESOLUTION
# ============================================================

def resolve_existing_file(
    preferred,
    alternatives
):
    """
    Resolve historical filename differences safely.

    We have built this repository incrementally, and a few processors
    have used slightly different output names over time.
    """

    if preferred.exists():
        return preferred

    for path in alternatives:

        if path.exists():
            return path

    return preferred


def resolve_input_files():
    """Resolve required processed inputs."""

    returning = resolve_existing_file(
        RETURNING_PRODUCTION_FILE,
        [
            PROJECT_ROOT
            / "data"
            / "processed"
            / "returning_production_metrics_2025.json",

            PROJECT_ROOT
            / "data"
            / "processed"
            / "processed_returning_production_2025.json",
        ]
    )

    transfer_talent = resolve_existing_file(
        TRANSFER_TALENT_FILE,
        [
            PROJECT_ROOT
            / "data"
            / "processed"
            / "transfer_talent_metrics_2025.json",
        ]
    )

    qb = resolve_existing_file(
        QB_CONTINUITY_FILE,
        [
            PROJECT_ROOT
            / "data"
            / "processed"
            / "qb_continuity_metrics_2025.json",
        ]
    )

    files = {
        "sp_2024":
            SP_2024_FILE,

        "gridiron_2024":
            GRIDIRON_2024_FILE,

        "gridiron_2025":
            GRIDIRON_2025_FILE,

        "returning":
            returning,

        "transfer_talent":
            transfer_talent,

        "transfer_production":
            TRANSFER_PRODUCTION_FILE,

        "qb":
            qb,

        "coaching":
            COACHING_FILE,
    }

    missing = [
        (
            name,
            path
        )
        for name, path in files.items()
        if not path.exists()
    ]

    if missing:

        print("=" * 78)

        print(
            "PRESEASON MODEL V4 INPUTS MISSING"
        )

        print("=" * 78)

        for (
            name,
            path
        ) in missing:

            print()

            print(
                f"{name}:"
            )

            print(
                f"  {path}"
            )

        raise FileNotFoundError(
            "One or more V4 model inputs are missing."
        )

    return files


# ============================================================
# FEATURE EXTRACTION
# ============================================================

def extract_returning_production(record):
    """
    Extract overall returning-production value.

    Supports several historical field names.
    """

    return first_available(
        record,
        [
            (
                "overall_returning_percentage",
            ),
            (
                "returning_percentage",
            ),
            (
                "returning_production",
            ),
            (
                "overall",
            ),
            (
                "overall_returning",
            ),
            (
                "returning",
            ),
        ]
    )


def extract_transfer_talent(record):
    """
    Extract net transfer talent.

    We prefer the already-processed net transfer measure.
    """

    direct = first_available(
        record,
        [
            (
                "net_transfer_talent",
            ),
            (
                "net_talent",
            ),
            (
                "net_elite_transfers",
            ),
            (
                "net",
                "talent"
            ),
            (
                "net",
                "effective_rating"
            ),
        ],
        default=0.0
    )

    if direct != 0.0:
        return direct

    incoming = first_available(
        record,
        [
            (
                "incoming_elite_count",
            ),
            (
                "incoming_090_count",
            ),
            (
                "incoming_high_end_count",
            ),
            (
                "incoming",
                "elite_count"
            ),
            (
                "incoming",
                "high_end_talent_count"
            ),
        ]
    )

    outgoing = first_available(
        record,
        [
            (
                "outgoing_elite_count",
            ),
            (
                "outgoing_090_count",
            ),
            (
                "outgoing_high_end_count",
            ),
            (
                "outgoing",
                "elite_count"
            ),
            (
                "outgoing",
                "high_end_talent_count"
            ),
        ]
    )

    return (
        incoming
        -
        outgoing
    )


def extract_transfer_production(record):
    """
    Extract V2 net offensive talent-production score.

    This was the strongest continuous transfer-production signal in
    historical validation.
    """

    qb_score = first_available(
        record,
        [
            (
                "net",
                "qb_talent_production_score"
            ),
        ]
    )

    skill_score = first_available(
        record,
        [
            (
                "net",
                "skill_talent_production_score"
            ),
        ]
    )

    return (
        qb_score
        +
        skill_score
    )


def extract_qb_continuity(record):
    """
    Extract the validated QB-continuity signal.

    Historical validation showed net usage-weighted QB value was the
    best of the tested QB continuity features.
    """

    return first_available(
        record,
        [
            (
                "net_usage_weighted_qb_value",
            ),
            (
                "net_usage_weighted_value",
            ),
            (
                "qb_continuity_score",
            ),
            (
                "net_qb_value",
            ),
        ]
    )


def extract_coaching(record):
    """
    Extract contextual coaching signal.

    Historical validation showed that a coaching change after a losing
    season provided the best incremental error reduction.
    """

    return first_available(
        record,
        [
            (
                "change_after_losing_season",
            ),
        ]
    )


# ============================================================
# SP+ MAPPING
# ============================================================

def calculate_sp_context(teams):
    """Calculate SP+ -> Gridiron mapping context."""

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
    """Map SP+ onto Project Gridiron rating scale."""

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

    return (
        context[
            "gridiron_mean"
        ]
        +
        sp_z
        *
        context[
            "gridiron_std"
        ]
    )


# ============================================================
# BUILD MODEL DATASET
# ============================================================

def build_records(files):
    """Build combined historical model records."""

    sp_lookup = build_lookup(
        load_json(
            files[
                "sp_2024"
            ]
        )
    )

    gridiron_2024_lookup = build_lookup(
        load_json(
            files[
                "gridiron_2024"
            ]
        )
    )

    gridiron_2025_lookup = build_lookup(
        load_json(
            files[
                "gridiron_2025"
            ]
        )
    )

    returning_lookup = build_lookup(
        load_json(
            files[
                "returning"
            ]
        )
    )

    transfer_talent_lookup = build_lookup(
        load_json(
            files[
                "transfer_talent"
            ]
        )
    )

    transfer_production_lookup = build_lookup(
        load_json(
            files[
                "transfer_production"
            ]
        )
    )

    qb_lookup = build_lookup(
        load_json(
            files[
                "qb"
            ]
        )
    )

    coaching_lookup = build_lookup(
        load_json(
            files[
                "coaching"
            ]
        )
    )

    teams = []

    for team_name in sorted(
        gridiron_2024_lookup
    ):

        if team_name not in gridiron_2025_lookup:
            continue

        if team_name not in sp_lookup:
            continue

        returning = returning_lookup.get(
            team_name,
            {}
        )

        transfer_talent = transfer_talent_lookup.get(
            team_name,
            {}
        )

        transfer_production = transfer_production_lookup.get(
            team_name,
            {}
        )

        qb = qb_lookup.get(
            team_name,
            {}
        )

        coaching = coaching_lookup.get(
            team_name,
            {}
        )

        teams.append(
            {
                "team":
                    team_name,

                "sp_2024":
                    safe_float(
                        sp_lookup[
                            team_name
                        ].get(
                            "rating"
                        )
                    ),

                "gridiron_2024":
                    safe_float(
                        gridiron_2024_lookup[
                            team_name
                        ].get(
                            "power_rating"
                        )
                    ),

                "actual_2025":
                    safe_float(
                        gridiron_2025_lookup[
                            team_name
                        ].get(
                            "power_rating"
                        )
                    ),

                "returning_production":
                    extract_returning_production(
                        returning
                    ),

                "transfer_talent":
                    extract_transfer_talent(
                        transfer_talent
                    ),

                "transfer_production":
                    extract_transfer_production(
                        transfer_production
                    ),

                "qb_continuity":
                    extract_qb_continuity(
                        qb
                    ),

                "coaching":
                    extract_coaching(
                        coaching
                    ),
            }
        )

    return teams


# ============================================================
# FEATURE CONTEXT
# ============================================================

FEATURE_KEYS = [
    "returning_production",
    "transfer_talent",
    "transfer_production",
    "qb_continuity",
    "coaching",
]


def calculate_feature_context(teams):
    """Calculate mean/std for each feature."""

    context = {}

    for key in FEATURE_KEYS:

        values = [
            team[
                key
            ]
            for team in teams
        ]

        context[
            key
        ] = {
            "mean":
                mean(
                    values
                ),

            "std":
                standard_deviation(
                    values
                ),

            "min":
                min(
                    values
                )
                if values
                else 0.0,

            "max":
                max(
                    values
                )
                if values
                else 0.0,
        }

    return context


# ============================================================
# MODEL EVALUATION
# ============================================================

def calculate_adjustment(
    team,
    feature_context,
    weights
):
    """Calculate combined preseason adjustment."""

    adjustment_parts = {}

    for key in FEATURE_KEYS:

        context = feature_context[
            key
        ]

        standardized = z_score(
            team[
                key
            ],
            context[
                "mean"
            ],
            context[
                "std"
            ],
        )

        contribution = (
            standardized
            *
            weights[
                key
            ]
        )

        adjustment_parts[
            key
        ] = contribution

    total = sum(
        adjustment_parts.values()
    )

    total = max(
        -MAX_TOTAL_ADJUSTMENT,
        min(
            total,
            MAX_TOTAL_ADJUSTMENT
        )
    )

    return (
        total,
        adjustment_parts,
    )


def evaluate_model(
    teams,
    sp_context,
    feature_context,
    weights
):
    """Evaluate one combined model."""

    predictions = []

    actuals = []

    adjustments = []

    for team in teams:

        baseline = map_sp_to_gridiron(
            team,
            sp_context
        )

        (
            adjustment,
            _
        ) = calculate_adjustment(
            team,
            feature_context,
            weights
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

        adjustments.append(
            adjustment
        )

    return {
        "weights":
            dict(
                weights
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

        "average_absolute_adjustment":
            mean(
                [
                    abs(
                        value
                    )
                    for value in adjustments
                ]
            ),

        "maximum_absolute_adjustment":
            max(
                [
                    abs(
                        value
                    )
                    for value in adjustments
                ]
            )
            if adjustments
            else 0.0,
    }


# ============================================================
# BASELINE
# ============================================================

def evaluate_baseline(
    teams,
    sp_context
):
    """Evaluate SP+ baseline."""

    predictions = [
        map_sp_to_gridiron(
            team,
            sp_context
        )
        for team in teams
    ]

    actuals = [
        team[
            "actual_2025"
        ]
        for team in teams
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
    }


# ============================================================
# MODEL SCORING
# ============================================================

def model_improves_all(
    model,
    baseline
):
    """Return whether model improves all three metrics."""

    return (
        model[
            "correlation"
        ]
        >
        baseline[
            "correlation"
        ]

        and

        model[
            "mae"
        ]
        <
        baseline[
            "mae"
        ]

        and

        model[
            "rmse"
        ]
        <
        baseline[
            "rmse"
        ]
    )


def model_score(
    model,
    baseline
):
    """
    Rank valid models.

    Correlation gains matter, but V4 also strongly rewards lower
    calibration error.

    A tiny complexity penalty discourages needlessly large adjustments.
    """

    correlation_gain = (
        model[
            "correlation"
        ]
        -
        baseline[
            "correlation"
        ]
    )

    mae_gain = (
        baseline[
            "mae"
        ]
        -
        model[
            "mae"
        ]
    )

    rmse_gain = (
        baseline[
            "rmse"
        ]
        -
        model[
            "rmse"
        ]
    )

    complexity_penalty = (
        model[
            "average_absolute_adjustment"
        ]
        *
        0.02
    )

    return (
        correlation_gain
        *
        100.0
        +
        mae_gain
        +
        rmse_gain
        -
        complexity_penalty
    )


# ============================================================
# GRID SEARCH
# ============================================================

def run_grid_search(
    teams,
    sp_context,
    feature_context,
    baseline
):
    """Run V4 parameter search."""

    results = []

    combinations = product(
        RETURNING_WEIGHTS,
        TRANSFER_TALENT_WEIGHTS,
        TRANSFER_PRODUCTION_WEIGHTS,
        QB_CONTINUITY_WEIGHTS,
        COACHING_WEIGHTS,
    )

    total_tested = 0

    for (
        returning_weight,
        transfer_talent_weight,
        transfer_production_weight,
        qb_weight,
        coaching_weight,
    ) in combinations:

        total_tested += 1

        weights = {
            "returning_production":
                returning_weight,

            "transfer_talent":
                transfer_talent_weight,

            "transfer_production":
                transfer_production_weight,

            "qb_continuity":
                qb_weight,

            "coaching":
                coaching_weight,
        }

        result = evaluate_model(
            teams,
            sp_context,
            feature_context,
            weights
        )

        result[
            "improves_all"
        ] = model_improves_all(
            result,
            baseline
        )

        if result[
            "improves_all"
        ]:

            result[
                "score"
            ] = model_score(
                result,
                baseline
            )

        else:

            result[
                "score"
            ] = None

        results.append(
            result
        )

    valid_results = [
        result
        for result in results
        if result[
            "improves_all"
        ]
    ]

    valid_results.sort(
        key=lambda result:
            result[
                "score"
            ],
        reverse=True,
    )

    return (
        total_tested,
        results,
        valid_results,
    )


# ============================================================
# TEAM DIAGNOSTICS
# ============================================================

def build_team_diagnostics(
    teams,
    sp_context,
    feature_context,
    best_model
):
    """Build team-level diagnostics for best model."""

    diagnostics = []

    weights = best_model[
        "weights"
    ]

    for team in teams:

        baseline = map_sp_to_gridiron(
            team,
            sp_context
        )

        (
            adjustment,
            parts,
        ) = calculate_adjustment(
            team,
            feature_context,
            weights
        )

        projection = (
            baseline
            +
            adjustment
        )

        actual = team[
            "actual_2025"
        ]

        diagnostics.append(
            {
                "team":
                    team[
                        "team"
                    ],

                "baseline":
                    baseline,

                "adjustment":
                    adjustment,

                "projection":
                    projection,

                "actual":
                    actual,

                "error":
                    projection
                    -
                    actual,

                "adjustment_parts":
                    parts,
            }
        )

    return diagnostics


# ============================================================
# MAIN
# ============================================================

def analyze():
    """Run combined preseason model V4."""

    files = resolve_input_files()

    teams = build_records(
        files
    )

    if not teams:

        raise ValueError(
            "No teams were available for preseason model V4."
        )

    sp_context = calculate_sp_context(
        teams
    )

    feature_context = calculate_feature_context(
        teams
    )

    baseline = evaluate_baseline(
        teams,
        sp_context
    )

    (
        combinations_tested,
        all_results,
        valid_results,
    ) = run_grid_search(
        teams,
        sp_context,
        feature_context,
        baseline
    )

    best_model = (
        valid_results[0]
        if valid_results
        else None
    )

    print("=" * 78)

    print(
        "PROJECT GRIDIRON PRESEASON MODEL V4"
    )

    print("=" * 78)

    print(
        f"Teams tested: "
        f"{len(teams)}"
    )

    print()

    print(
        "SP+ BASELINE"
    )

    print("-" * 78)

    print(
        f"Correlation: "
        f"{baseline['correlation']:.4f}"
    )

    print(
        f"MAE: "
        f"{baseline['mae']:.2f}"
    )

    print(
        f"RMSE: "
        f"{baseline['rmse']:.2f}"
    )

    print()

    print(
        "FEATURES"
    )

    print("-" * 78)

    print(
        "Returning production"
    )

    print(
        "Transfer talent"
    )

    print(
        "Transfer production / experience"
    )

    print(
        "QB continuity"
    )

    print(
        "Contextual coaching change"
    )

    print()

    print(
        "FEATURE DISTRIBUTIONS"
    )

    print("-" * 78)

    for key in FEATURE_KEYS:

        context = feature_context[
            key
        ]

        print(
            f"{key}: "
            f"mean={context['mean']:.4f}, "
            f"std={context['std']:.4f}, "
            f"min={context['min']:.4f}, "
            f"max={context['max']:.4f}"
        )

    print()

    print(
        "GRID SEARCH"
    )

    print("-" * 78)

    print(
        f"Parameter combinations tested: "
        f"{combinations_tested}"
    )

    print(
        f"Models improving all three metrics: "
        f"{len(valid_results)}"
    )

    print()

    print(
        "TOP 20 VALID V4 MODELS"
    )

    print("-" * 78)

    for rank, result in enumerate(
        valid_results[:20],
        start=1
    ):

        weights = result[
            "weights"
        ]

        print(
            f"{rank}. "
            f"RP={weights['returning_production']:.2f}, "
            f"TT={weights['transfer_talent']:.2f}, "
            f"TP={weights['transfer_production']:.2f}, "
            f"QB={weights['qb_continuity']:.2f}, "
            f"COACH={weights['coaching']:.2f}, "
            f"corr={result['correlation']:.4f}, "
            f"MAE={result['mae']:.2f}, "
            f"RMSE={result['rmse']:.2f}, "
            f"avg_adj="
            f"{result['average_absolute_adjustment']:.2f}"
        )

    print()

    print(
        "BEST COMBINED MODEL"
    )

    print("-" * 78)

    if best_model is None:

        print(
            "No tested combined model improved "
            "correlation, MAE, and RMSE simultaneously."
        )

        diagnostics = []

    else:

        weights = best_model[
            "weights"
        ]

        print(
            f"Returning production: "
            f"{weights['returning_production']:.2f} pts/std"
        )

        print(
            f"Transfer talent: "
            f"{weights['transfer_talent']:.2f} pts/std"
        )

        print(
            f"Transfer production: "
            f"{weights['transfer_production']:.2f} pts/std"
        )

        print(
            f"QB continuity: "
            f"{weights['qb_continuity']:.2f} pts/std"
        )

        print(
            f"Coaching: "
            f"{weights['coaching']:.2f} pts/std"
        )

        print()

        print(
            f"Baseline correlation: "
            f"{baseline['correlation']:.4f}"
        )

        print(
            f"V4 correlation: "
            f"{best_model['correlation']:.4f}"
        )

        print(
            f"Correlation improvement: "
            f"{best_model['correlation'] - baseline['correlation']:+.4f}"
        )

        print()

        print(
            f"Baseline MAE: "
            f"{baseline['mae']:.2f}"
        )

        print(
            f"V4 MAE: "
            f"{best_model['mae']:.2f}"
        )

        print(
            f"MAE improvement: "
            f"{baseline['mae'] - best_model['mae']:+.2f}"
        )

        print()

        print(
            f"Baseline RMSE: "
            f"{baseline['rmse']:.2f}"
        )

        print(
            f"V4 RMSE: "
            f"{best_model['rmse']:.2f}"
        )

        print(
            f"RMSE improvement: "
            f"{baseline['rmse'] - best_model['rmse']:+.2f}"
        )

        print()

        print(
            f"Average absolute adjustment: "
            f"{best_model['average_absolute_adjustment']:.2f}"
        )

        print(
            f"Maximum absolute adjustment: "
            f"{best_model['maximum_absolute_adjustment']:.2f}"
        )

        diagnostics = build_team_diagnostics(
            teams,
            sp_context,
            feature_context,
            best_model
        )

        print()

        print(
            "BIGGEST POSITIVE V4 ADJUSTMENTS"
        )

        print("-" * 78)

        positive = sorted(
            diagnostics,
            key=lambda record:
                record[
                    "adjustment"
                ],
            reverse=True,
        )

        for record in positive[:15]:

            parts = record[
                "adjustment_parts"
            ]

            print(
                f"{record['team']}: "
                f"{record['baseline']:.2f} -> "
                f"{record['projection']:.2f} "
                f"({record['adjustment']:+.2f}), "
                f"actual={record['actual']:.2f}, "
                f"RP={parts['returning_production']:+.2f}, "
                f"TT={parts['transfer_talent']:+.2f}, "
                f"TP={parts['transfer_production']:+.2f}, "
                f"QB={parts['qb_continuity']:+.2f}, "
                f"coach={parts['coaching']:+.2f}"
            )

        print()

        print(
            "BIGGEST NEGATIVE V4 ADJUSTMENTS"
        )

        print("-" * 78)

        negative = sorted(
            diagnostics,
            key=lambda record:
                record[
                    "adjustment"
                ]
        )

        for record in negative[:15]:

            parts = record[
                "adjustment_parts"
            ]

            print(
                f"{record['team']}: "
                f"{record['baseline']:.2f} -> "
                f"{record['projection']:.2f} "
                f"({record['adjustment']:+.2f}), "
                f"actual={record['actual']:.2f}, "
                f"RP={parts['returning_production']:+.2f}, "
                f"TT={parts['transfer_talent']:+.2f}, "
                f"TP={parts['transfer_production']:+.2f}, "
                f"QB={parts['qb_continuity']:+.2f}, "
                f"coach={parts['coaching']:+.2f}"
            )

        print()

        print(
            "LARGEST V4 MODEL ERRORS"
        )

        print("-" * 78)

        largest_errors = sorted(
            diagnostics,
            key=lambda record:
                abs(
                    record[
                        "error"
                    ]
                ),
            reverse=True,
        )

        for record in largest_errors[:15]:

            print(
                f"{record['team']}: "
                f"projection={record['projection']:.2f}, "
                f"actual={record['actual']:.2f}, "
                f"error={record['error']:+.2f}, "
                f"adjustment={record['adjustment']:+.2f}"
            )

    output = {
        "season":
            2025,

        "teams_tested":
            len(teams),

        "baseline":
            baseline,

        "feature_context":
            feature_context,

        "parameter_combinations_tested":
            combinations_tested,

        "valid_model_count":
            len(
                valid_results
            ),

        "best_model":
            best_model,

        "top_models":
            valid_results[:50],

        "team_diagnostics":
            diagnostics,
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
