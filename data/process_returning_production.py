"""
Process CFBD returning production data into model-ready team profiles.

The data represents production returning into the specified season.

Example:
    2025 returning production describes production returning
    from the 2024 season into 2025.

Usage:
    python -m data.process_returning_production 2025
    python -m data.process_returning_production 2026
"""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def input_file(year):
    """Return raw input path for a season."""

    return (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "returning_production"
        / f"{year}.json"
    )


def output_file(year):
    """Return processed output path for a season."""

    return (
        PROJECT_ROOT
        / "data"
        / "processed"
        / f"returning_production_{year}.json"
    )


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


def process_team(record):
    """
    Convert one CFBD record into a standardized team profile.

    CFBD currently returns fields such as:
        percentPPA
        percentPassingPPA
        percentReceivingPPA
        percentRushingPPA
        usage
        passingUsage
        receivingUsage
        rushingUsage
    """

    return {
        "season":
            record.get(
                "season"
            ),

        "team":
            record.get(
                "team"
            ),

        "conference":
            record.get(
                "conference"
            ),

        "overall": {
            "percent":
                safe_float(
                    record.get(
                        "percentPPA"
                    )
                ),

            "usage":
                safe_float(
                    record.get(
                        "usage"
                    )
                ),

            "ppa":
                safe_float(
                    record.get(
                        "totalPPA"
                    )
                ),
        },

        "passing": {
            "percent":
                safe_float(
                    record.get(
                        "percentPassingPPA"
                    )
                ),

            "usage":
                safe_float(
                    record.get(
                        "passingUsage"
                    )
                ),

            "ppa":
                safe_float(
                    record.get(
                        "totalPassingPPA"
                    )
                ),
        },

        "rushing": {
            "percent":
                safe_float(
                    record.get(
                        "percentRushingPPA"
                    )
                ),

            "usage":
                safe_float(
                    record.get(
                        "rushingUsage"
                    )
                ),

            "ppa":
                safe_float(
                    record.get(
                        "totalRushingPPA"
                    )
                ),
        },

        "receiving": {
            "percent":
                safe_float(
                    record.get(
                        "percentReceivingPPA"
                    )
                ),

            "usage":
                safe_float(
                    record.get(
                        "receivingUsage"
                    )
                ),

            "ppa":
                safe_float(
                    record.get(
                        "totalReceivingPPA"
                    )
                ),
        },
    }


def process_returning_production(year):
    """Process all returning-production records for one season."""

    source = input_file(
        year
    )

    destination = output_file(
        year
    )

    if not source.exists():

        raise FileNotFoundError(
            f"Returning production input file not found: "
            f"{source}"
        )

    with source.open(
        "r",
        encoding="utf-8"
    ) as file:

        raw_records = json.load(
            file
        )

    processed = []

    for record in raw_records:

        team = process_team(
            record
        )

        if not team[
            "team"
        ]:
            continue

        processed.append(
            team
        )

    processed.sort(
        key=lambda team:
            team[
                "team"
            ]
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with destination.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            processed,
            file,
            indent=4
        )

    non_zero = [
        team
        for team in processed
        if team[
            "overall"
        ][
            "percent"
        ] > 0
    ]

    values = [
        team[
            "overall"
        ][
            "percent"
        ]
        for team in processed
    ]

    print("=" * 70)

    print(
        f"{year} RETURNING PRODUCTION PROCESSING"
    )

    print("=" * 70)

    print(
        f"Processed "
        f"{len(processed)} "
        f"returning production profiles."
    )

    print(
        f"Saved to {destination}"
    )

    print()

    print(
        f"Teams with non-zero overall "
        f"returning production: "
        f"{len(non_zero)}"
    )

    if values:

        print(
            f"Minimum overall returning production: "
            f"{min(values):.3f}"
        )

        print(
            f"Maximum overall returning production: "
            f"{max(values):.3f}"
        )

        print(
            f"Average overall returning production: "
            f"{sum(values) / len(values):.3f}"
        )

    print()

    print(
        "TOP 10 RETURNING PRODUCTION"
    )

    print("-" * 70)

    highest = sorted(
        processed,
        key=lambda team:
            team[
                "overall"
            ][
                "percent"
            ],
        reverse=True,
    )

    for team in highest[:10]:

        print(
            f"{team['team']}: "
            f"{team['overall']['percent']:.3f}"
        )


if __name__ == "__main__":

    year = 2025

    if len(sys.argv) > 1:

        year = int(
            sys.argv[1]
        )

    process_returning_production(
        year
    )
