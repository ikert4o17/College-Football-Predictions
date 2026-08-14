"""
Analyze continuity between 2024 and 2025 power ratings.

This script does not modify any ratings.
It measures how strongly a team's 2024 rating
carries into its 2025 rating.
"""

import json
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


def load_json(path):
    """Load a JSON file."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def build_lookup(records):
    """Create a team-to-rating lookup."""

    return {
        record["team"]: record
        for record in records
    }


def calculate_correlation(x_values, y_values):
    """Calculate Pearson correlation."""

    if len(x_values) < 2:
        return 0.0

    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)

    numerator = sum(
        (x - x_mean) * (y - y_mean)
        for x, y in zip(
            x_values,
            y_values
        )
    )

    x_sum = sum(
        (x - x_mean) ** 2
        for x in x_values
    )

    y_sum = sum(
        (y - y_mean) ** 2
        for y in y_values
    )

    denominator = math.sqrt(
        x_sum * y_sum
    )

    if denominator == 0:
        return 0.0

    return numerator / denominator


def analyze_continuity():
    """Analyze rating continuity between seasons."""

    ratings_2024 = load_json(
        RATINGS_2024_FILE
    )

    ratings_2025 = load_json(
        RATINGS_2025_FILE
    )

    lookup_2024 = build_lookup(
        ratings_2024
    )

    lookup_2025 = build_lookup(
        ratings_2025
    )

    common_teams = sorted(
        set(lookup_2024)
        & set(lookup_2025)
    )

    comparisons = []

    for team in common_teams:

        rating_2024 = lookup_2024[
            team
        ]["power_rating"]

        rating_2025 = lookup_2025[
            team
        ]["power_rating"]

        change = (
            rating_2025
            - rating_2024
        )

        comparisons.append(
            {
                "team": team,
                "rating_2024": rating_2024,
                "rating_2025": rating_2025,
                "change": change,
                "absolute_change":
                    abs(change),
            }
        )

    comparisons.sort(
        key=lambda team:
            team["rating_2025"],
        reverse=True,
    )

    x_values = [
        comparison["rating_2024"]
        for comparison in comparisons
    ]

    y_values = [
        comparison["rating_2025"]
        for comparison in comparisons
    ]

    correlation = calculate_correlation(
        x_values,
        y_values
    )

    average_2024 = (
        sum(x_values)
        / len(x_values)
    )

    average_2025 = (
        sum(y_values)
        / len(y_values)
    )

    average_absolute_change = (
        sum(
            comparison["absolute_change"]
            for comparison in comparisons
        )
        / len(comparisons)
    )

    biggest_risers = sorted(
        comparisons,
        key=lambda team:
            team["change"],
        reverse=True,
    )[:10]

    biggest_fallers = sorted(
        comparisons,
        key=lambda team:
            team["change"],
    )[:10]

    print(
        "=" * 60
    )

    print(
        "2024 → 2025 POWER RATING CONTINUITY"
    )

    print(
        "=" * 60
    )

    print(
        f"2024 ratings loaded: "
        f"{len(ratings_2024)}"
    )

    print(
        f"2025 ratings loaded: "
        f"{len(ratings_2025)}"
    )

    print(
        f"Teams in both seasons: "
        f"{len(comparisons)}"
    )

    print(
        f"Average 2024 rating: "
        f"{average_2024:.2f}"
    )

    print(
        f"Average 2025 rating: "
        f"{average_2025:.2f}"
    )

    print(
        f"Average absolute rating change: "
        f"{average_absolute_change:.2f}"
    )

    print(
        f"Pearson correlation: "
        f"{correlation:.4f}"
    )

    print()

    print(
        "BIGGEST RISERS"
    )

    print(
        "-" * 60
    )

    for team in biggest_risers:

        print(
            f"{team['team']}: "
            f"{team['rating_2024']:.2f} → "
            f"{team['rating_2025']:.2f} "
            f"({team['change']:+.2f})"
        )

    print()

    print(
        "BIGGEST FALLERS"
    )

    print(
        "-" * 60
    )

    for team in biggest_fallers:

        print(
            f"{team['team']}: "
            f"{team['rating_2024']:.2f} → "
            f"{team['rating_2025']:.2f} "
            f"({team['change']:+.2f})"
        )

    print()

    print(
        "TOP 10 TEAMS BY 2025 RATING"
    )

    print(
        "-" * 60
    )

    for team in comparisons[:10]:

        print(
            f"{team['team']}: "
            f"2024={team['rating_2024']:.2f}, "
            f"2025={team['rating_2025']:.2f}, "
            f"change={team['change']:+.2f}"
        )


if __name__ == "__main__":
    analyze_continuity()
