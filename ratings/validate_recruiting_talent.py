"""
Validate whether 2025 recruiting talent helps explain
2024 -> 2025 team improvement and improves a preseason baseline.

This module tests several recruiting signals:

- Average recruit rating
- Top-10 average recruit rating
- Top-20 average recruit rating
- Blue-chip count
- Elite recruit count
- Five-star count
- Four-star count

It then tests small recruiting weights against the 2024
power rating as a baseline for predicting the 2025 power rating.

This module does NOT modify the production power-rating system.
"""

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RECRUITING_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "recruiting_talent_2025.json"
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
]


def load_json(path):
    """Load a JSON file."""

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
    """Build one analysis record per matching team."""

    recruiting = load_json(
        RECRUITING_FILE
    )

    ratings_2024 = load_json(
        RATINGS_2024_FILE
    )

    ratings_2025 = load_json(
        RATINGS_2025_FILE
    )

    recruiting_lookup = build_lookup(
        recruiting
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

        if team_name not in recruiting_lookup:
            continue

        recruit = recruiting_lookup[
            team_name
        ]

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

                "total_recruits":
                    safe_float(
                        recruit.get(
                            "total_recruits"
                        )
                    ),

                "average_rating":
                    safe_float(
                        recruit.get(
                            "average_rating"
                        )
                    ),

                "top_10_average_rating":
                    safe_float(
                        recruit.get(
                            "top_10_average_rating"
                        )
                    ),

                "top_20_average_rating":
                    safe_float(
                        recruit.get(
                            "top_20_average_rating"
                        )
                    ),

                "blue_chip_count":
                    safe_float(
                        recruit.get(
                            "blue_chip_count"
                        )
                    ),

                "elite_count":
                    safe_float(
                        recruit.get(
                            "elite_count"
                        )
                    ),

                "five_star_count":
                    safe_float(
                        recruit.get(
                            "five_star_count"
                        )
                    ),

                "four_star_count":
                    safe_float(
                        recruit.get(
                            "four_star_count"
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
    """Calculate one recruiting metric's correlation with rating change."""

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
    """Test whether a recruiting metric improves the baseline."""

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

            recruiting_score = normalize_value(
                metric_values,
                team[
                    metric_key
                ]
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
                recruiting_score
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
    """Run recruiting talent validation."""

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

    baseline_correlation = (
        pearson_correlation(
            rating_2024_values,
            rating_2025_values
        )
    )

    print("=" * 70)

    print(
        "RECRUITING TALENT VALIDATION"
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
        "RECRUITING METRICS VS "
        "2024 -> 2025 RATING CHANGE"
    )

    print("-" * 70)

    metrics = [
        (
            "total_recruits",
            "Total recruits"
        ),
        (
            "average_rating",
            "Average recruit rating"
        ),
        (
            "top_10_average_rating",
            "Top-10 average recruit rating"
        ),
        (
            "top_20_average_rating",
            "Top-20 average recruit rating"
        ),
        (
            "blue_chip_count",
            "Blue-chip count"
        ),
        (
            "elite_count",
            "Elite recruit count"
        ),
        (
            "five_star_count",
            "Five-star count"
        ),
        (
            "four_star_count",
            "Four-star count"
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
        "STRONGEST RECRUITING SIGNALS"
    )

    print("-" * 70)

    for result in (
        usable_results[:8]
    ):

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

    for result in usable_results:

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
                "RESULT: Recruiting talent "
                "adds predictive value."
            )

        else:

            print(
                "RESULT: No tested recruiting "
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
            f"top10="
            f"{team['top_10_average_rating']:.4f}, "
            f"blue_chips="
            f"{team['blue_chip_count']:.0f}, "
            f"elite="
            f"{team['elite_count']:.0f}"
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
            f"top10="
            f"{team['top_10_average_rating']:.4f}, "
            f"blue_chips="
            f"{team['blue_chip_count']:.0f}, "
            f"elite="
            f"{team['elite_count']:.0f}"
        )


if __name__ == "__main__":
    analyze()
