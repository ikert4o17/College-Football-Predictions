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

        "overall": {
            "percent": record.get(
                "percentReturning",
                0
            ),
            "usage": record.get(
                "usageReturning",
                0
            ),
            "ppa": record.get(
                "ppaReturning",
                0
            ),
        },

        "passing": {
            "percent": record.get(
                "percentReturningPassing",
                0
            ),
            "usage": record.get(
                "usageReturningPassing",
                0
            ),
            "ppa": record.get(
                "ppaReturningPassing",
                0
            ),
        },

        "rushing": {
            "percent": record.get(
                "percentReturningRushing",
                0
            ),
            "usage": record.get(
                "usageReturningRushing",
                0
            ),
            "ppa": record.get(
                "ppaReturningRushing",
                0
            ),
        },

        "receiving": {
            "percent": record.get(
                "percentReturningReceiving",
                0
            ),
            "usage": record.get(
                "usageReturningReceiving",
                0
            ),
            "ppa": record.get(
                "ppaReturningReceiving",
                0
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


if __name__ == "__main__":
    process_returning_production()
