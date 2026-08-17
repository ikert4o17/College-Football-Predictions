"""
Validate whether transfer portal talent improves preseason ratings.

This module tests whether 2025 transfer portal activity helps explain
2025 team performance beyond the existing 2025 power rating.

It does NOT modify the existing power-rating system.
"""

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RATINGS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "power_ratings_2025.json"
)

TRANSFER_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "transfer_portal_2025.json"
)

RESULTS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "team_results_2025.json"
)


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


def pearson_correlation(x_values, y_values):
    """Calculate Pearson correlation."""

    if len(x_values) != len(y_values):
        return None

    if len(x_values) < 2:
        return None

    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)

    numerator = sum(
        (x - x_mean) * (y - y_mean)
        for x, y in zip(
            x_values,
            y_values
        )
    )

    x_variance = sum(
        (x - x_mean) ** 2
        for x in x_values
    )

    y_variance = sum(
        (y - y_mean) ** 2
        for y in y_values
    )

    denominator = math.sqrt(
        x_variance * y_variance
    )

    if denominator == 0:
        return None

    return numerator / denominator


def calculate_actual_performance(result):
    """Calculate the validation target."""

    point_margin = result.get(
        "point_margin_per_game",
        0
    )

    win_percentage = result.get(
        "win_percentage",
        0
    )

    return (
        point_margin * 0.75
        +
        win_percentage * 0.25
    )


def safe_float(value):
    """Convert a value to float safely."""

    if value is None:
        return 0.0

    try:
        return float(value)
    except (
        TypeError,
        ValueError
    ):
        return 0.0


def analyze():
    """Validate transfer portal metrics."""

    ratings = load_json(
        RATINGS_FILE
    )

    transfers = load_json(
        TRANSFER_FILE
    )

    results = load_json(
        RESULTS_FILE
    )

    rating_lookup = build_lookup(
        ratings
    )

    transfer_lookup = build_lookup(
        transfers
    )

    result_lookup = build_lookup(
        results
    )

    teams = []

    for team_name in sorted(
        rating_lookup
    ):

        if team_name not in transfer_lookup:
            continue

        if team_name not in result_lookup:
            continue

        rating = rating_lookup[
            team_name
        ]

        transfer = transfer_lookup[
            team_name
        ]

        result = result_lookup[
            team_name
        ]

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

        actual = calculate_actual_performance(
            result
        )

        teams.append(
            {
                "team": team_name,

                "rating":
                    safe_float(
                        rating.get(
                            "power_rating",
                            0
                        )
                    ),

                "actual":
                    actual,

                "incoming_count":
                    safe_float(
                        incoming.get(
                            "count",
                            0
                        )
                    ),

                "outgoing_count":
                    safe_float(
                        outgoing.get(
                            "count",
                            0
                        )
                    ),

                "net_count":
                    safe_float(
                        net.get(
                            "transfer_count",
                            0
                        )
                    ),

                "incoming_rated_count":
                    safe_float(
                        incoming.get(
                            "rated_count",
                            0
                        )
                    ),

                "outgoing_rated_count":
                    safe_float(
                        outgoing.get(
                            "rated_count",
                            0
                        )
                    ),

                "incoming_rating":
                    safe_float(
                        incoming.get(
                            "total_rating",
                            0
                        )
                    ),

                "outgoing_rating":
                    safe_float(
                        outgoing.get(
                            "total_rating",
                            0
                        )
                    ),

                "net_rating":
                    safe_float(
                        net.get(
                            "rating_difference",
                            0
                        )
                    ),

                "incoming_average_rating":
                    safe_float(
                        incoming.get(
                            "average_rating",
                            0
                        )
                    ),

                "outgoing_average_rating":
                    safe_float(
                        outgoing.get(
                            "average_rating",
                            0
                        )
                    ),

                "incoming_stars":
                    safe_float(
                        incoming.get(
                            "total_stars",
                            0
                        )
                    ),

                "outgoing_stars":
                    safe_float(
                        outgoing.get(
                            "total_stars",
                            0
                        )
                    ),

                "net_stars":
                    safe_float(
                        net.get(
                            "star_difference",
                            0
                        )
                    ),
            }
        )

    if not teams:
        print(
            "No matching teams found."
        )
        return

    actual_values = [
        team["actual"]
        for team in teams
    ]

    rating_values = [
        team["rating"]
        for team in teams
    ]

    baseline_correlation = pearson_correlation(
        rating_values,
        actual_values
    )

    print("=" * 60)
    print(
        "TRANSFER PORTAL PRESEASON VALIDATION"
    )
    print("=" * 60)

    print(
        f"Teams tested: {len(teams)}"
    )

    print()

    print(
        "BASELINE VS ACTUAL PERFORMANCE"
    )
    print("-" * 60)

    if baseline_correlation is None:
        print(
            "Baseline correlation: N/A"
        )
    else:
        print(
            f"Baseline power-rating correlation: "
            f"{baseline_correlation:.4f}"
        )

    print()

    metrics = [
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
            "incoming_rated_count",
            "Incoming rated transfer count"
        ),
        (
            "outgoing_rated_count",
            "Outgoing rated transfer count"
        ),
        (
            "incoming_rating",
            "Incoming transfer rating"
        ),
        (
            "outgoing_rating",
            "Outgoing transfer rating"
        ),
        (
            "net_rating",
            "Net transfer rating"
        ),
        (
            "incoming_average_rating",
            "Incoming average transfer rating"
        ),
        (
            "outgoing_average_rating",
            "Outgoing average transfer rating"
        ),
        (
            "incoming_stars",
            "Incoming transfer stars"
        ),
        (
            "outgoing_stars",
            "Outgoing transfer stars"
        ),
        (
            "net_stars",
            "Net transfer stars"
        ),
    ]

    print(
        "TRANSFER METRIC CORRELATIONS"
    )
    print("-" * 60)

    correlations = {}

    for metric_key, metric_name in metrics:

        values = [
            team[metric_key]
            for team in teams
        ]

        correlation = pearson_correlation(
            values,
            actual_values
        )

        correlations[
            metric_key
        ] = correlation

        if correlation is None:
            print(
                f"{metric_name}: N/A"
            )
        else:
            print(
                f"{metric_name}: "
                f"{correlation:.4f}"
            )

    print()

    print(
        "COMBINED MODEL TESTS"
    )
    print("-" * 60)

    # We test several simple combinations rather than choosing
    # a final weighting prematurely.

    combination_tests = [
        (
            "Baseline + net transfer rating",
            "net_rating",
            0.05,
        ),
        (
            "Baseline + incoming transfer rating",
            "incoming_rating",
            0.05,
        ),
        (
            "Baseline + net transfer stars",
            "net_stars",
            0.05,
        ),
        (
            "Baseline + incoming transfer stars",
            "incoming_stars",
            0.05,
        ),
        (
            "Baseline + net transfer count",
            "net_count",
            0.05,
        ),
    ]

    for name, metric_key, weight in combination_tests:

        metric_values = [
            team[metric_key]
            for team in teams
        ]

        minimum = min(
            metric_values
        )

        maximum = max(
            metric_values
        )

        combined_values = []

        for team in teams:

            value = team[
                metric_key
            ]

            if maximum == minimum:
                normalized = 0.5
            else:
                normalized = (
                    value - minimum
                ) / (
                    maximum - minimum
                )

            transfer_score = (
                normalized * 100
            )

            combined = (
                team["rating"]
                * (1 - weight)
                +
                transfer_score
                * weight
            )

            combined_values.append(
                combined
            )

        correlation = pearson_correlation(
            combined_values,
            actual_values
        )

        if (
            baseline_correlation is None
            or correlation is None
        ):
            improvement = None
        else:
            improvement = (
                correlation
                -
                baseline_correlation
            )

        if correlation is None:
            print(
                f"{name}: N/A"
            )
        else:
            print(
                f"{name}: "
                f"{correlation:.4f} "
                f"(change="
                f"{improvement:+.4f})"
            )

    print()

    print(
        "TRANSFER DISTRIBUTION"
    )
    print("-" * 60)

    print(
        f"Average incoming transfers: "
        f"{sum(team['incoming_count'] for team in teams) / len(teams):.2f}"
    )

    print(
        f"Average outgoing transfers: "
        f"{sum(team['outgoing_count'] for team in teams) / len(teams):.2f}"
    )

    print(
        f"Average net transfers: "
        f"{sum(team['net_count'] for team in teams) / len(teams):.2f}"
    )

    print(
        f"Average incoming transfer rating: "
        f"{sum(team['incoming_rating'] for team in teams) / len(teams):.2f}"
    )

    print(
        f"Average outgoing transfer rating: "
        f"{sum(team['outgoing_rating'] for team in teams) / len(teams):.2f}"
    )

    print()

    print(
        "TOP TEAMS BY NET TRANSFER RATING"
    )
    print("-" * 60)

    highest = sorted(
        teams,
        key=lambda team:
            team["net_rating"],
        reverse=True,
    )

    for team in highest[:10]:

        print(
            f"{team['team']}: "
            f"net_rating="
            f"{team['net_rating']:+.2f}, "
            f"incoming="
            f"{team['incoming_count']:.0f}, "
            f"outgoing="
            f"{team['outgoing_count']:.0f}, "
            f"actual="
            f"{team['actual']:.2f}"
        )

    print()

    print(
        "BOTTOM TEAMS BY NET TRANSFER RATING"
    )
    print("-" * 60)

    lowest = sorted(
        teams,
        key=lambda team:
            team["net_rating"],
    )

    for team in lowest[:10]:

        print(
            f"{team['team']}: "
            f"net_rating="
            f"{team['net_rating']:+.2f}, "
            f"incoming="
            f"{team['incoming_count']:.0f}, "
            f"outgoing="
            f"{team['outgoing_count']:.0f}, "
            f"actual="
            f"{team['actual']:.2f}"
        )


if __name__ == "__main__":
    analyze()
