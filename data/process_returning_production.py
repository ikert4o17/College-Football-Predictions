"""
Process CFBD returning production data into model-ready team profiles.

The data represents production returning into the specified season.
For 2025, this describes the production returning from the 2024 season.
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


def process_team(record):
    """Convert one CFBD record into a standardized team profile."""

    return {
        "season": record.get("season"),
        "team": record.get("team"),
        "conference": record.get("conference"),

        "overall": {
            "percent_ppa":
                record.get("percentPPA", 0),

            "usage":
                record.get("usage", 0),

            "total_ppa":
                record.get("totalPPA", 0),
        },

        "passing": {
            "percent_ppa":
                record.get("percentPassingPPA", 0),

            "usage":
                record.get("passingUsage", 0),

            "total_ppa":
                record.get("totalPassingPPA", 0),
        },

        "rushing": {
            "percent_ppa":
                record.get("percentRushingPPA", 0),

            "usage":
                record.get("rushingUsage", 0),

            "total_ppa":
                record.get("totalRushingPPA", 0),
        },

        "receiving": {
            "percent_ppa":
                record.get("percentReceivingPPA", 0),

            "usage":
                record.get("receivingUsage", 0),

            "total_ppa":
                record.get("totalReceivingPPA", 0),
        },
    }


def process_returning_production():
    """Process all returning production records."""

    with INPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        raw_records = json.load(file)

    if not raw_records:
        raise ValueError(
            "No returning production records were found."
        )

    print(
        "CFBD returning production fields:"
    )

    for key in sorted(raw_records[0].keys()):
        print(f"  {key}")

    processed = []

    for record in raw_records:

        team = process_team(record)

        if team["team"] is None:
            continue

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

    if processed:
        print(
            "\nSample processed record:"
        )

        print(
            json.dumps(
                processed[0],
                indent=4
            )
        )


if __name__ == "__main__":
    process_returning_production()
