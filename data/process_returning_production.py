"""
Process CFBD returning production data into model-ready team profiles.

CFBD's /player/returning endpoint provides returning production
as PPA percentages and returning usage percentages.

For 2025, these values describe production returning from the
2024 season into the 2025 season.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "returning_production"
    / "2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "returning_production_2025.json"
)


def to_float(value):
    """Safely convert a value to float."""

    if value is None:
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def process_team(record):
    """Convert one CFBD record into a standardized team profile."""

    team_name = record.get("team")

    if not team_name:
        return None

    return {
        "season": record.get("season"),
        "team": team_name,
        "conference": record.get("conference"),

        "overall": {
            "percent": to_float(
                record.get("percentPPA", 0)
            ),
            "usage": to_float(
                record.get("usage", 0)
            ),
        },

        "passing": {
            "percent": to_float(
                record.get("percentPassingPPA", 0)
            ),
            "usage": to_float(
                record.get("passingUsage", 0)
            ),
        },

        "rushing": {
            "percent": to_float(
                record.get("percentRushingPPA", 0)
            ),
            "usage": to_float(
                record.get("rushingUsage", 0)
            ),
        },

        "receiving": {
            "percent": to_float(
                record.get("percentReceivingPPA", 0)
            ),
            "usage": to_float(
                record.get("receivingUsage", 0)
            ),
        },

        "raw": {
            "total_ppa": to_float(
                record.get("totalPPA", 0)
            ),
            "total_passing_ppa": to_float(
                record.get("totalPassingPPA", 0)
            ),
            "total_receiving_ppa": to_float(
                record.get("totalReceivingPPA", 0)
            ),
            "total_rushing_ppa": to_float(
                record.get("totalRushingPPA", 0)
            ),
        },
    }


def process_returning_production():
    """Process all returning production records."""

    with INPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        raw_records = json.load(file)

    processed = []

    for record in raw_records:

        team = process_team(record)

        if team is not None:
            processed.append(team)

    processed.sort(
        key=lambda team:
            team["team"]
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            processed,
            file,
            indent=4
        )

    print(
        f"Processed "
        f"{len(processed)} "
        f"returning production profiles."
    )

    print(
        f"Saved to {OUTPUT_FILE}"
    )

    nonzero_overall = [
        team["overall"]["percent"]
        for team in processed
        if team["overall"]["percent"] != 0
    ]

    print(
        f"Teams with non-zero overall returning production: "
        f"{len(nonzero_overall)}"
    )

    if nonzero_overall:

        print(
            f"Minimum overall returning production: "
            f"{min(nonzero_overall):.3f}"
        )

        print(
            f"Maximum overall returning production: "
            f"{max(nonzero_overall):.3f}"
        )

        print(
            f"Average overall returning production: "
            f"{sum(nonzero_overall) / len(nonzero_overall):.3f}"
        )

        print()

        highest = sorted(
            processed,
            key=lambda team:
                team["overall"]["percent"],
            reverse=True,
        )

        print(
            "Top 5 returning production:"
        )

        for team in highest[:5]:

            print(
                f"{team['team']}: "
                f"{team['overall']['percent']:.3f}"
            )

    else:

        print(
            "WARNING: No non-zero returning production "
            "values were found."
        )

        if raw_records:

            print(
                "First raw CFBD record:"
            )

            print(
                json.dumps(
                    raw_records[0],
                    indent=4
                )
            )


if __name__ == "__main__":
    process_returning_production()
