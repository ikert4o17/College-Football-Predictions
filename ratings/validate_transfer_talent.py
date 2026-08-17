"""
Validate whether composite-weighted transfer talent helps explain
2024 -> 2025 team improvement and improves a preseason baseline.

This module tests:

- Incoming and outgoing transfer volume
- Incoming and outgoing average composite ratings
- Average-rating difference
- High-end transfer talent
- Total portal churn
- Above-replacement transfer talent across several thresholds

It then tests whether the strongest transfer metrics improve the
2024 power rating as a predictor of the 2025 power rating.

This module does NOT modify the production power-rating system.
"""

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

ENRICHED_TRANSFER_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "enriched_transfer_portal_2025.json"
)

TRANSFER_TALENT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "transfer_talent_2025.json"
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


REPLACEMENT_THRESHOLDS = [
    0.80,
    0.82,
    0.84,
    0.85,
    0.86,
    0.88,
    0.90,
]


COMBINED_WEIGHTS = [
    0.02,
    0.05,
    0.10,
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
    """Convert a value safely to float."""

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return None


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
    """Normalize one value to 0-100."""

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


def create_threshold_profile():
    """Create an empty above-replacement profile."""

    profile = {}

    for threshold in REPLACEMENT_THRESHOLDS:

        key = (
            f"{threshold:.2f}"
        )

        profile[key] = {
            "incoming": 0.0,
            "outgoing": 0.0,
            "net": 0.0,
        }

    return profile


def build_above_replacement_profiles(
    transfers
):
    """
    Calculate talent above replacement level.

    Example with 0.85 threshold:

    0.95 player = 0.10 above replacement
    0.90 player = 0.05 above replacement
    0.85 player = 0.00
    0.82 player = 0.00

    Only talent ABOVE the threshold contributes here.
    """

    teams = {}

    def ensure_team(team):

        if not team:
            return

        if team not in teams:

            teams[team] = (
                create_threshold_profile()
            )

    for transfer in transfers:

        origin = transfer.get(
            "origin"
        )

        destination = transfer.get(
            "destination"
        )

        ensure_team(
            origin
        )

        ensure_team(
            destination
        )

        talent = transfer.get(
            "talent",
            {}
        )

        rating = safe_float(
            talent.get(
                "effective_rating"
            )
        )

        if rating is None:
            continue

        for threshold in (
            REPLACEMENT_THRESHOLDS
        ):

            key = (
                f"{threshold:.2f}"
            )

            above_replacement = max(
                rating - threshold,
                0.0
            )

            if destination:

                teams[
                    destination
                ][
                    key
                ][
                    "incoming"
                ] += (
                    above_replacement
                )

            if origin:

                teams[
                    origin
                ][
                    key
                ][
                    "outgoing"
                ] += (
                    above_replacement
                )

    for team_profile in (
        teams.values()
    ):

        for threshold in (
            REPLACEMENT_THRESHOLDS
        ):

            key = (
                f"{threshold:.2f}"
            )

            incoming = (
                team_profile[
                    key
                ][
                    "incoming"
                ]
            )

            outgoing = (
                team_profile[
                    key
                ][
                    "outgoing"
                ]
            )

            team_profile[
                key
            ][
                "net"
            ] = (
                incoming
                -
                outgoing
            )

    return teams


def build_analysis_records():
    """Build one complete analysis record per team."""

    transfers = load_json(
        ENRICHED_TRANSFER_FILE
    )

    transfer_talent = load_json(
        TRANSFER_TALENT_FILE
    )

    ratings_2024 = load_json(
        RATINGS_2024_FILE
    )

    ratings_2025 = load_json(
        RATINGS_2025_FILE
    )

    transfer_lookup = (
        build_lookup(
            transfer_talent
        )
    )

    rating_2024_lookup = (
        build_lookup(
            ratings_2024
        )
    )

    rating_2025_lookup = (
        build_lookup(
            ratings_2025
        )
    )

    above_replacement = (
        build_above_replacement_profiles(
            transfers
        )
    )

    teams = []

    for team_name in sorted(
        rating_2024_lookup
    ):

        if (
            team_name
            not in rating_2025_lookup
        ):
            continue

        if (
            team_name
            not in transfer_lookup
        ):
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

        if (
            rating_2024 is None
            or rating_2025 is None
        ):
            continue

        transfer = (
            transfer_lookup[
                team_name
            ]
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

        incoming_count = (
            safe_float(
                incoming.get(
                    "count"
                )
            )
            or 0
        )

        outgoing_count = (
            safe_float(
                outgoing.get(
                    "count"
                )
            )
            or 0
        )

        incoming_average = (
            safe_float(
                incoming.get(
                    "average_rating"
                )
            )
            or 0
        )

        outgoing_average = (
            safe_float(
                outgoing.get(
                    "average_rating"
                )
            )
            or 0
        )

        record = {
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

            "incoming_count":
                incoming_count,

            "outgoing_count":
                outgoing_count,

            "net_count":
                incoming_count
                -
                outgoing_count,

            "total_churn":
                incoming_count
                +
                outgoing_count,

            "incoming_average_rating":
                incoming_average,

            "outgoing_average_rating":
                outgoing_average,

            "average_rating_difference":
                incoming_average
                -
                outgoing_average,

            "incoming_high_end":
                safe_float(
                    incoming.get(
                        "high_end_count"
                    )
                )
                or 0,

            "outgoing_high_end":
                safe_float(
                    outgoing.get(
                        "high_end_count"
                    )
                )
                or 0,

            "net_high_end":
                safe_float(
                    net.get(
                        "high_end_count"
                    )
                )
                or 0,

            "raw_net_rating_sum":
                safe_float(
                    net.get(
                        "rating_sum"
                    )
                )
                or 0,
        }

        threshold_profile = (
            above_replacement.get(
                team_name,
                {}
            )
        )

        for threshold in (
            REPLACEMENT_THRESHOLDS
        ):

            key = (
                f"{threshold:.2f}"
            )

            profile = (
                threshold_profile.get(
                    key,
                    {
                        "incoming": 0.0,
                        "outgoing": 0.0,
                        "net": 0.0,
                    }
                )
            )

            record[
                f"above_{key}_incoming"
            ] = (
                profile[
                    "incoming"
                ]
            )

            record[
                f"above_{key}_outgoing"
            ] = (
                profile[
                    "outgoing"
                ]
            )

            record[
                f"above_{key}_net"
            ] = (
                profile[
                    "net"
                ]
            )

        teams.append(
            record
        )

    return teams


def correlation_report(
    teams,
    metric_key,
    metric_name
):
    """Calculate one metric's correlation with rating change."""

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

    correlation = (
        pearson_correlation(
            x_values,
            y_values
        )
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
    """Test whether a transfer metric improves the preseason baseline."""

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

            metric_score = (
                normalize_value(
                    metric_values,
                    team[
                        metric_key
                    ]
                )
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
                metric_score
                *
                weight
            )

            combined_values.append(
                combined
            )

        correlation = (
            pearson_correlation(
                combined_values,
                target_values
            )
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
    """Run transfer-talent validation."""

    teams = (
        build_analysis_records()
    )

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
        "COMPOSITE-WEIGHTED TRANSFER TALENT VALIDATION"
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
        "TRANSFER METRICS VS "
        "2024 -> 2025 RATING CHANGE"
    )

    print("-" * 70)

    base_metrics = [
        (
            "incoming_count",
            "Incoming transfer count"
        ),
        (
            "outgoing_count",
            "Outgoing transfer count"
        ),
        (
            "net_count",
            "Net transfer count"
        ),
        (
            "total_churn",
            "Total portal churn"
        ),
        (
            "incoming_average_rating",
            "Incoming average composite"
        ),
        (
            "outgoing_average_rating",
            "Outgoing average composite"
        ),
        (
            "average_rating_difference",
            "Incoming - outgoing average composite"
        ),
        (
            "incoming_high_end",
            "Incoming 0.90+ transfers"
        ),
        (
            "outgoing_high_end",
            "Outgoing 0.90+ transfers"
        ),
        (
            "net_high_end",
            "Net 0.90+ transfer count"
        ),
        (
            "raw_net_rating_sum",
            "Raw net rating sum"
        ),
    ]

    metric_results = []

    for (
        metric_key,
        metric_name
    ) in base_metrics:

        correlation = (
            correlation_report(
                teams,
                metric_key,
                metric_name
            )
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

    print()

    print(
        "ABOVE-REPLACEMENT TALENT TESTS"
    )

    print("-" * 70)

    for threshold in (
        REPLACEMENT_THRESHOLDS
    ):

        key = (
            f"{threshold:.2f}"
        )

        incoming_key = (
            f"above_{key}_incoming"
        )

        outgoing_key = (
            f"above_{key}_outgoing"
        )

        net_key = (
            f"above_{key}_net"
        )

        print(
            f"Replacement threshold: "
            f"{threshold:.2f}"
        )

        incoming_correlation = (
            correlation_report(
                teams,
                incoming_key,
                (
                    "  Incoming "
                    "above-replacement talent"
                )
            )
        )

        outgoing_correlation = (
            correlation_report(
                teams,
                outgoing_key,
                (
                    "  Outgoing "
                    "above-replacement talent"
                )
            )
        )

        net_correlation = (
            correlation_report(
                teams,
                net_key,
                (
                    "  Net "
                    "above-replacement talent"
                )
            )
        )

        metric_results.append(
            {
                "metric_key":
                    net_key,

                "metric_name":
                    (
                        "Net above-replacement "
                        f"talent ({threshold:.2f})"
                    ),

                "correlation":
                    net_correlation,
            }
        )

        print()

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

    print(
        "STRONGEST TRANSFER SIGNALS"
    )

    print("-" * 70)

    for result in (
        usable_results[:10]
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

    candidate_metrics = (
        usable_results[:8]
    )

    combined_results = []

    for result in candidate_metrics:

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

        best = (
            valid_combined[0]
        )

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
                "RESULT: Transfer talent "
                "adds predictive value."
            )

        else:

            print(
                "RESULT: No tested transfer "
                "talent metric improves the baseline."
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
            f"in_avg="
            f"{team['incoming_average_rating']:.4f}, "
            f"out_avg="
            f"{team['outgoing_average_rating']:.4f}, "
            f"high_end_net="
            f"{team['net_high_end']:+.0f}"
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
            f"in_avg="
            f"{team['incoming_average_rating']:.4f}, "
            f"out_avg="
            f"{team['outgoing_average_rating']:.4f}, "
            f"high_end_net="
            f"{team['net_high_end']:+.0f}"
        )


if __name__ == "__main__":
    analyze()
