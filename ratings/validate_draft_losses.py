"""
Validate whether NFL Draft losses help explain
2024 -> 2025 team decline and improve a preseason baseline.

This module tests several draft-loss signals:

- Total drafted players
- First-round picks
- Day 1 / Day 2 / Day 3 losses
- Top-50 and Top-100 picks
- Pre-draft grade totals and averages
- Draft capital
- Drafted quarterback losses
- First-round quarterback losses

Draft-loss metrics are treated as NEGATIVE adjustments to the
2024 baseline when testing prediction of the 2025 power rating.

This module does NOT modify the production power-rating system.
"""

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DRAFT_LOSSES_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "draft_losses_2025.json"
)

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


COMBINED_WEIGHTS = [
    0.01,
    0.02,
    0.03,
    0.05,
    0.10,
]


def load_json(path):
    """Load JSON data."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def build_lookup(records):
    """Create a team lookup."""

    return {
        record["team"]: record
        for record in records
    }


def safe_float(value):
    """Safely convert a value to float."""

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

    return (
        numerator
        /
        denominator
    )


def normalize_value(
    values,
    value
):
    """Normalize one value to a 0-100 range."""

    minimum = min(
        values
    )

    maximum = max(
        values
    )

    if maximum == minimum:
        return 50.0

    return (
        (
            value - minimum
        )
        /
        (
            maximum - minimum
        )
        *
        100
    )


def build_analysis_records():
    """Build one analysis record per team."""

    draft_losses = load_json(
        DRAFT_LOSSES_FILE
    )

    ratings_2024 = load_json(
        RATINGS_2024_FILE
    )

    ratings_2025 = load_json(
        RATINGS_2025_FILE
    )

    draft_lookup = build_lookup(
        draft_losses
    )

    rating_2024_lookup = build_lookup(
        ratings_2024
    )

    rating_2025_lookup = build_lookup(
        ratings_2025
    )

    teams = []

    for team_name in sorted(
        rating_2024_lookup
    ):

        if team_name not in rating_2025_lookup:
            continue

        rating_2024 = safe_float(
            rating_2024_lookup[
                team_name
            ].get(
                "power_rating"
            )
        )

        rating_2025 = safe_float(
            rating_2025_lookup[
                team_name
            ].get(
                "power_rating"
            )
        )

        draft = draft_lookup.get(
            team_name,
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

                "drafted_count":
                    safe_float(
                        draft.get(
                            "drafted_count"
                        )
                    ),

                "round_1_count":
                    safe_float(
                        draft.get(
                            "round_1_count"
                        )
                    ),

                "day_1_count":
                    safe_float(
                        draft.get(
                            "day_1_count"
                        )
                    ),

                "day_2_count":
                    safe_float(
                        draft.get(
                            "day_2_count"
                        )
                    ),

                "day_3_count":
                    safe_float(
                        draft.get(
                            "day_3_count"
                        )
                    ),

                "top_10_count":
                    safe_float(
                        draft.get(
                            "top_10_count"
                        )
                    ),

                "top_25_count":
                    safe_float(
                        draft.get(
                            "top_25_count"
                        )
                    ),

                "top_50_count":
                    safe_float(
                        draft.get(
                            "top_50_count"
                        )
                    ),

                "top_100_count":
                    safe_float(
                        draft.get(
                            "top_100_count"
                        )
                    ),

                "pre_draft_grade_sum":
                    safe_float(
                        draft.get(
                            "pre_draft_grade_sum"
                        )
                    ),

                "pre_draft_grade_average":
                    safe_float(
                        draft.get(
                            "pre_draft_grade_average"
                        )
                    ),

                "draft_capital":
                    safe_float(
                        draft.get(
                            "draft_capital"
                        )
                    ),

                "qb_drafted_count":
                    safe_float(
                        draft.get(
                            "qb_drafted_count"
                        )
                    ),

                "qb_round_1_count":
                    safe_float(
                        draft.get(
                            "qb_round_1_count"
                        )
                    ),
            }
        )

    return teams


def correlation_report(
    teams,
    metric_key,
    metric_name
):
    """Calculate correlation with year-over-year rating change."""

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

    correlation = pearson_correlation(
        x_values,
        y_values
    )

    if correlation is None:

        print(
            f"{metric_name}: N/A"
        )

    else:

        print(
            f"{metric_name}: "
            f"{correlation:+.4f}"
        )

    return correlation


def combined_model_test(
    teams,
    metric_key,
    metric_name,
    baseline_correlation
):
    """
    Test a draft-loss metric as a negative preseason adjustment.
    """

    metric_values = [
        team[
            metric_key
        ]
        for team in teams
    ]

    target_values = [
        team[
            "rating_2025"
        ]
        for team in teams
    ]

    results = []

    for weight in COMBINED_WEIGHTS:

        combined_values = []

        for team in teams:

            loss_score = normalize_value(
                metric_values,
                team[
                    metric_key
                ]
            )

            # Higher draft-loss score should LOWER
            # the projected next-season rating.
            inverse_loss_score = (
                100.0
                -
                loss_score
            )

            combined = (
                team[
                    "rating_2024"
                ]
                *
                (
                    1 - weight
                )
                +
                inverse_loss_score
                *
                weight
            )

            combined_values.append(
                combined
            )

        correlation = pearson_correlation(
            combined_values,
            target_values
        )

        if (
            correlation is None
            or baseline_correlation is None
        ):

            improvement = None

        else:

            improvement = (
                correlation
                -
                baseline_correlation
            )

        results.append(
            {
                "metric":
                    metric_name,

                "metric_key":
                    metric_key,

                "weight":
                    weight,

                "correlation":
                    correlation,

                "improvement":
                    improvement,
            }
        )

    return results


def analyze():
    """Run NFL Draft loss validation."""

    teams = build_analysis_records()

    if not teams:

        print(
            "No matching teams found."
        )

        return

    rating_2024_values = [
        team[
            "rating_2024"
        ]
        for team in teams
    ]

    rating_2025_values = [
        team[
            "rating_2025"
        ]
        for team in teams
    ]

    baseline_correlation = pearson_correlation(
        rating_2024_values,
        rating_2025_values
    )

    print("=" * 70)

    print(
        "NFL DRAFT LOSS VALIDATION"
    )

    print("=" * 70)

    print(
        f"Teams tested: "
        f"{len(teams)}"
    )

    print()

    print(
        "2024 BASELINE VS 2025 RATING"
    )

    print("-" * 70)

    if baseline_correlation is None:

        print(
            "Baseline correlation: N/A"
        )

    else:

        print(
            f"Baseline correlation: "
            f"{baseline_correlation:.4f}"
        )

    print()

    print(
        "DRAFT LOSS METRICS VS "
        "2024 -> 2025 RATING CHANGE"
    )

    print("-" * 70)

    metrics = [
        (
            "drafted_count",
            "Total drafted players"
        ),
        (
            "round_1_count",
            "First-round picks"
        ),
        (
            "day_1_count",
            "Day 1 picks"
        ),
        (
            "day_2_count",
            "Day 2 picks"
        ),
        (
            "day_3_count",
            "Day 3 picks"
        ),
        (
            "top_10_count",
            "Top-10 picks"
        ),
        (
            "top_25_count",
            "Top-25 picks"
        ),
        (
            "top_50_count",
            "Top-50 picks"
        ),
        (
            "top_100_count",
            "Top-100 picks"
        ),
        (
            "pre_draft_grade_sum",
            "Pre-draft grade sum"
        ),
        (
            "pre_draft_grade_average",
            "Average pre-draft grade"
        ),
        (
            "draft_capital",
            "Draft capital"
        ),
        (
            "qb_drafted_count",
            "Drafted quarterbacks"
        ),
        (
            "qb_round_1_count",
            "First-round quarterbacks"
        ),
    ]

    metric_results = []

    for (
        metric_key,
        metric_name
    ) in metrics:

        correlation = correlation_report(
            teams,
            metric_key,
            metric_name
        )

        metric_results.append(
            {
                "metric_key":
                    metric_key,

                "metric_name":
                    metric_name,

                "correlation":
                    correlation,
            }
        )

    usable_results = [
        result
        for result in metric_results
        if result[
            "correlation"
        ] is not None
    ]

    usable_results.sort(
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
        "STRONGEST DRAFT-LOSS SIGNALS"
    )

    print("-" * 70)

    for result in usable_results[:10]:

        print(
            f"{result['metric_name']}: "
            f"{result['correlation']:+.4f}"
        )

    print()

    print(
        "COMBINED PRESEASON MODEL TESTS"
    )

    print("-" * 70)

    combined_results = []

    for result in usable_results[:10]:

        tests = combined_model_test(
            teams,
            result[
                "metric_key"
            ],
            result[
                "metric_name"
            ],
            baseline_correlation
        )

        combined_results.extend(
            tests
        )

        for test in tests:

            correlation = test[
                "correlation"
            ]

            improvement = test[
                "improvement"
            ]

            if (
                correlation is None
                or improvement is None
            ):
                continue

            print(
                f"{test['metric']} "
                f"@ {test['weight'] * 100:.0f}%: "
                f"{correlation:.4f} "
                f"(change="
                f"{improvement:+.4f})"
            )

    valid_combined = [
        result
        for result in combined_results
        if (
            result[
                "correlation"
            ] is not None
            and result[
                "improvement"
            ] is not None
        )
    ]

    valid_combined.sort(
        key=lambda result:
            result[
                "improvement"
            ],
        reverse=True,
    )

    print()

    print(
        "BEST COMBINED RESULT"
    )

    print("-" * 70)

    if valid_combined:

        best = valid_combined[0]

        print(
            f"Metric: "
            f"{best['metric']}"
        )

        print(
            f"Weight: "
            f"{best['weight'] * 100:.0f}%"
        )

        print(
            f"Baseline correlation: "
            f"{baseline_correlation:.4f}"
        )

        print(
            f"Combined correlation: "
            f"{best['correlation']:.4f}"
        )

        print(
            f"Improvement: "
            f"{best['improvement']:+.4f}"
        )

        if (
            best[
                "improvement"
            ] > 0
        ):

            print(
                "RESULT: NFL Draft losses "
                "add predictive value."
            )

        else:

            print(
                "RESULT: No tested draft-loss "
                "metric improves the baseline."
            )

    print()

    print(
        "BIGGEST POSITIVE RATING CHANGES"
    )

    print("-" * 70)

    biggest_risers = sorted(
        teams,
        key=lambda team:
            team[
                "rating_change"
            ],
        reverse=True,
    )

    for team in biggest_risers[:10]:

        print(
            f"{team['team']}: "
            f"{team['rating_2024']:.2f} -> "
            f"{team['rating_2025']:.2f} "
            f"({team['rating_change']:+.2f}), "
            f"drafted="
            f"{team['drafted_count']:.0f}, "
            f"R1="
            f"{team['round_1_count']:.0f}, "
            f"capital="
            f"{team['draft_capital']:.2f}, "
            f"QB="
            f"{team['qb_drafted_count']:.0f}"
        )

    print()

    print(
        "BIGGEST NEGATIVE RATING CHANGES"
    )

    print("-" * 70)

    biggest_fallers = sorted(
        teams,
        key=lambda team:
            team[
                "rating_change"
            ],
    )

    for team in biggest_fallers[:10]:

        print(
            f"{team['team']}: "
            f"{team['rating_2024']:.2f} -> "
            f"{team['rating_2025']:.2f} "
            f"({team['rating_change']:+.2f}), "
            f"drafted="
            f"{team['drafted_count']:.0f}, "
            f"R1="
            f"{team['round_1_count']:.0f}, "
            f"capital="
            f"{team['draft_capital']:.2f}, "
            f"QB="
            f"{team['qb_drafted_count']:.0f}"
        )


if __name__ == "__main__":
    analyze()
