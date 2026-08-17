"""
Validate whether returning production improves preseason ratings.

This module tests whether 2025 returning production can improve
predictions of 2026 team performance.

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

RETURNING_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "returning_production_2025.json"
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


def get_returning_percent(record):
    """Get overall returning production percentage."""

    overall = record.get(
        "overall",
        {}
    )

    value = overall.get(
        "percent",
        0
    )

    if value is None:
        return 0

    return float(value)


def normalize(values, value):
    """Normalize a value to a 0-1 range."""

    minimum = min(values)
    maximum = max(values)

    if maximum == minimum:
        return 0.5

    return (
        (value - minimum)
        / (maximum - minimum)
    )


def calculate_actual_performance(result):
    """
    Calculate a simple measure of actual 2025 performance.

    The existing team-results module already provides these values,
    so we use point margin and win percentage as the validation target.
    """

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


def analyze():
    """Validate returning production against actual performance."""

    ratings = load_json(
        RATINGS_FILE
    )

    returning = load_json(
        RETURNING_FILE
    )

    results = load_json(
        RESULTS_FILE
    )

    rating_lookup = build_lookup(
        ratings
    )

    returning_lookup = build_lookup(
        returning
    )

    result_lookup = build_lookup(
        results
    )

    teams = []

    for team_name in sorted(
        rating_lookup
    ):

        if team_name not in returning_lookup:
            continue

        if team_name not in result_lookup:
            continue

        rating = rating_lookup[
            team_name
        ]

        returning_record = returning_lookup[
            team_name
        ]

        result = result_lookup[
            team_name
        ]

        returning_percent = get_returning_percent(
            returning_record
        )

        actual_performance = calculate_actual_performance(
            result
        )

        teams.append(
            {
                "team": team_name,
                "rating": rating["power_rating"],
                "returning": returning_percent,
                "actual_performance": actual_performance,
                "point_margin": result.get(
                    "point_margin_per_game",
                    0
                ),
                "win_percentage": result.get(
                    "win_percentage",
                    0
                ),
            }
        )

    if not teams:
        print("No matching teams found.")
        return

    returning_values = [
        team["returning"]
        for team in teams
    ]

    actual_values = [
        team["actual_performance"]
        for team in teams
    ]

    rating_values = [
        team["rating"]
        for team in teams
    ]

    rating_correlation = pearson_correlation(
        rating_values,
        actual_values
    )

    returning_correlation = pearson_correlation(
        returning_values,
        actual_values
    )

    combined_values = []

    for team in teams:

        returning_score = normalize(
            returning_values,
            team["returning"]
        )

        combined_score = (
            team["rating"] * 0.90
            +
            returning_score * 10.0 * 0.10
        )

        combined_values.append(
            combined_score
        )

    combined_correlation = pearson_correlation(
        combined_values,
        actual_values
    )

    print("=" * 60)
    print(
        "RETURNING PRODUCTION PRESEASON VALIDATION"
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

    if rating_correlation is None:
        print("Baseline correlation: N/A")
    else:
        print(
            f"Baseline power-rating correlation: "
            f"{rating_correlation:.4f}"
        )

    print()

    print(
        "RETURNING PRODUCTION VS ACTUAL PERFORMANCE"
    )
    print("-" * 60)

    if returning_correlation is None:
        print("Returning production correlation: N/A")
    else:
        print(
            f"Returning production correlation: "
            f"{returning_correlation:.4f}"
        )

    print()

    print(
        "COMBINED MODEL TEST"
    )
    print("-" * 60)

    if combined_correlation is None:
        print("Combined correlation: N/A")
    else:
        print(
            f"Baseline + returning production: "
            f"{combined_correlation:.4f}"
        )

    if (
        rating_correlation is not None
        and combined_correlation is not None
    ):
        improvement = (
            combined_correlation
            - rating_correlation
        )

        print(
            f"Correlation improvement: "
            f"{improvement:+.4f}"
        )

        if improvement > 0:
            print(
                "RESULT: Returning production "
                "improves the baseline."
            )
        elif improvement < 0:
            print(
                "RESULT: Returning production "
                "hurts the baseline."
            )
        else:
            print(
                "RESULT: Returning production "
                "provides no measurable improvement."
            )

    print()

    print(
        "RETURNING PRODUCTION DISTRIBUTION"
    )
    print("-" * 60)

    print(
        f"Minimum: {min(returning_values):.2f}"
    )

    print(
        f"Maximum: {max(returning_values):.2f}"
    )

    print(
        f"Average: "
        f"{sum(returning_values) / len(returning_values):.2f}"
    )

    print()

    print(
        "TOP RETURNING PRODUCTION"
    )
    print("-" * 60)

    highest = sorted(
        teams,
        key=lambda team:
            team["returning"],
        reverse=True,
    )

    for team in highest[:10]:

        print(
            f"{team['team']}: "
            f"returning={team['returning']:.2f}, "
            f"rating={team['rating']:.2f}, "
            f"actual={team['actual_performance']:.2f}"
        )

    print()

    print(
        "LOWEST RETURNING PRODUCTION"
    )
    print("-" * 60)

    lowest = sorted(
        teams,
        key=lambda team:
            team["returning"],
    )

    for team in lowest[:10]:

        print(
            f"{team['team']}: "
            f"returning={team['returning']:.2f}, "
            f"rating={team['rating']:.2f}, "
            f"actual={team['actual_performance']:.2f}"
        )


if __name__ == "__main__":
    analyze()
