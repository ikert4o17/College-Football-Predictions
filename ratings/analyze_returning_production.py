"""
Analyze whether returning production explains
2024 -> 2025 power-rating changes.

This is an analysis-only module.

It does NOT modify the existing power-rating system.
"""

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RETURNING_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "returning_production_2025.json"
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


def percentile(values, percentile):
    """Calculate a percentile using linear interpolation."""

    if not values:
        return 0

    values = sorted(values)

    if len(values) == 1:
        return values[0]

    position = (
        (len(values) - 1)
        * percentile
    )

    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return values[lower]

    weight = position - lower

    return (
        values[lower]
        * (1 - weight)
        +
        values[upper]
        * weight
    )


def analyze():
    """Analyze returning production against rating changes."""

    returning_records = load_json(
        RETURNING_FILE
    )

    ratings_2024 = load_json(
        RATINGS_2024_FILE
    )

    ratings_2025 = load_json(
        RATINGS_2025_FILE
    )

    returning_lookup = build_lookup(
        returning_records
    )

    rating_2024_lookup = build_lookup(
        ratings_2024
    )

    rating_2025_lookup = build_lookup(
        ratings_2025
    )

    teams = []

    for team_name in sorted(
        returning_lookup
    ):

        if team_name not in rating_2024_lookup:
            continue

        if team_name not in rating_2025_lookup:
            continue

        returning = returning_lookup[
            team_name
        ]

        rating_2024 = rating_2024_lookup[
            team_name
        ]

        rating_2025 = rating_2025_lookup[
            team_name
        ]

        rating_change = (
            rating_2025["power_rating"]
            -
            rating_2024["power_rating"]
        )

        teams.append(
            {
                "team": team_name,

                "rating_2024":
                    rating_2024[
                        "power_rating"
                    ],

                "rating_2025":
                    rating_2025[
                        "power_rating"
                    ],

                "rating_change":
                    rating_change,

                "overall_percent":
                    returning[
                        "overall"
                    ]["percent"],

                "overall_usage":
                    returning[
                        "overall"
                    ]["usage"],

                "overall_ppa":
                    returning[
                        "overall"
                    ]["ppa"],

                "passing_percent":
                    returning[
                        "passing"
                    ]["percent"],

                "passing_usage":
                    returning[
                        "passing"
                    ]["usage"],

                "passing_ppa":
                    returning[
                        "passing"
                    ]["ppa"],

                "rushing_percent":
                    returning[
                        "rushing"
                    ]["percent"],

                "rushing_usage":
                    returning[
                        "rushing"
                    ]["usage"],

                "rushing_ppa":
                    returning[
                        "rushing"
                    ]["ppa"],

                "receiving_percent":
                    returning[
                        "receiving"
                    ]["percent"],

                "receiving_usage":
                    returning[
                        "receiving"
                    ]["usage"],

                "receiving_ppa":
                    returning[
                        "receiving"
                    ]["ppa"],
            }
        )

    if not teams:
        print("No matching teams found.")
        return

    print("=" * 60)
    print(
        "RETURNING PRODUCTION VS "
        "2024 → 2025 POWER-RATING CHANGE"
    )
    print("=" * 60)

    print(
        f"Returning production records: "
        f"{len(returning_records)}"
    )

    print(
        f"Teams with both ratings and "
        f"returning production: "
        f"{len(teams)}"
    )

    print()

    metrics = [
        (
            "overall_percent",
            "Overall returning production %"
        ),
        (
            "overall_usage",
            "Overall returning usage"
        ),
        (
            "overall_ppa",
            "Overall returning PPA"
        ),
        (
            "passing_percent",
            "Passing returning production %"
        ),
        (
            "passing_usage",
            "Passing returning usage"
        ),
        (
            "passing_ppa",
            "Passing returning PPA"
        ),
        (
            "rushing_percent",
            "Rushing returning production %"
        ),
        (
            "rushing_usage",
            "Rushing returning usage"
        ),
        (
            "rushing_ppa",
            "Rushing returning PPA"
        ),
        (
            "receiving_percent",
            "Receiving returning production %"
        ),
        (
            "receiving_usage",
            "Receiving returning usage"
        ),
        (
            "receiving_ppa",
            "Receiving returning PPA"
        ),
    ]

    print(
        "CORRELATION WITH RATING CHANGE"
    )
    print("-" * 60)

    for metric_key, metric_name in metrics:

        x_values = [
            team[metric_key]
            for team in teams
        ]

        y_values = [
            team["rating_change"]
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
                f"{correlation:.4f}"
            )

    print()

    print(
        "RETURNING PRODUCTION DISTRIBUTION"
    )
    print("-" * 60)

    overall_values = [
        team["overall_percent"]
        for team in teams
    ]

    print(
        f"Overall returning production "
        f"minimum: "
        f"{min(overall_values):.2f}"
    )

    print(
        f"Overall returning production "
        f"25th percentile: "
        f"{percentile(overall_values, 0.25):.2f}"
    )

    print(
        f"Overall returning production "
        f"median: "
        f"{percentile(overall_values, 0.50):.2f}"
    )

    print(
        f"Overall returning production "
        f"75th percentile: "
        f"{percentile(overall_values, 0.75):.2f}"
    )

    print(
        f"Overall returning production "
        f"maximum: "
        f"{max(overall_values):.2f}"
    )

    print()

    # Sort by overall returning production.
    highest_returning = sorted(
        teams,
        key=lambda team:
            team["overall_percent"],
        reverse=True,
    )

    lowest_returning = sorted(
        teams,
        key=lambda team:
            team["overall_percent"],
    )

    print(
        "HIGHEST RETURNING PRODUCTION"
    )
    print("-" * 60)

    for team in highest_returning[:10]:

        print(
            f"{team['team']}: "
            f"returning="
            f"{team['overall_percent']:.2f}, "
            f"rating change="
            f"{team['rating_change']:+.2f}"
        )

    print()

    print(
        "LOWEST RETURNING PRODUCTION"
    )
    print("-" * 60)

    for team in lowest_returning[:10]:

        print(
            f"{team['team']}: "
            f"returning="
            f"{team['overall_percent']:.2f}, "
            f"rating change="
            f"{team['rating_change']:+.2f}"
        )

    print()

    # Compare teams in the top and bottom quartiles.
    cutoff_low = percentile(
        overall_values,
        0.25
    )

    cutoff_high = percentile(
        overall_values,
        0.75
    )

    low_group = [
        team
        for team in teams
        if team["overall_percent"]
        <= cutoff_low
    ]

    high_group = [
        team
        for team in teams
        if team["overall_percent"]
        >= cutoff_high
    ]

    low_average = (
        sum(
            team["rating_change"]
            for team in low_group
        )
        / len(low_group)
        if low_group
        else 0
    )

    high_average = (
        sum(
            team["rating_change"]
            for team in high_group
        )
        / len(high_group)
        if high_group
        else 0
    )

    print(
        "QUARTILE COMPARISON"
    )
    print("-" * 60)

    print(
        f"Lowest 25% returning production "
        f"average rating change: "
        f"{low_average:+.2f}"
    )

    print(
        f"Highest 25% returning production "
        f"average rating change: "
        f"{high_average:+.2f}"
    )

    print(
        f"Difference between groups: "
        f"{high_average - low_average:+.2f}"
    )

    print()

    # Show teams with the largest rating changes
    # and their returning production.
    biggest_changes = sorted(
        teams,
        key=lambda team:
            abs(team["rating_change"]),
        reverse=True,
    )

    print(
        "LARGEST 2024 → 2025 RATING CHANGES"
    )
    print("-" * 60)

    for team in biggest_changes[:15]:

        print(
            f"{team['team']}: "
            f"{team['rating_2024']:.2f} → "
            f"{team['rating_2025']:.2f} "
            f"({team['rating_change']:+.2f}), "
            f"returning="
            f"{team['overall_percent']:.2f}"
        )


if __name__ == "__main__":
    analyze()
