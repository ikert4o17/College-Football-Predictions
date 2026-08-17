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


def get_value(record, *names):
    """
    Return the first matching value from a CFBD record.

    CFBD field names can change between API versions, so we
    support several possible naming conventions.
    """

    for name in names:
        if name in record and record[name] is not None:
            return record[name]

    return 0


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

        "overall": {
            "percent": to_float(
                get_value(
                    record,
                    "percentReturning",
                    "percent_returning",
                )
            ),
            "usage": to_float(
                get_value(
                    record,
                    "usageReturning",
                    "usage_returning",
                )
            ),
            "ppa": to_float(
                get_value(
                    record,
                    "ppaReturning",
                    "ppa_returning",
                )
            ),
        },

        "passing": {
            "percent": to_float(
                get_value(
                    record,
                    "percentReturningPassing",
                    "percent_returning_passing",
                )
            ),
            "usage": to_float(
                get_value(
                    record,
                    "usageReturningPassing",
                    "usage_returning_passing",
                )
            ),
            "ppa": to_float(
                get_value(
                    record,
                    "ppaReturningPassing",
                    "ppa_returning_passing",
                )
            ),
        },

        "rushing": {
            "percent": to_float(
                get_value(
                    record,
                    "percentReturningRushing",
                    "percent_returning_rushing",
                )
            ),
            "usage": to_float(
                get_value(
                    record,
                    "usageReturningRushing",
                    "usage_returning_rushing",
                )
            ),
            "ppa": to_float(
                get_value(
                    record,
                    "ppaReturningRushing",
                    "ppa_returning_rushing",
                )
            ),
        },

        "receiving": {
            "percent": to_float(
                get_value(
                    record,
                    "percentReturningReceiving",
                    "percent_returning_receiving",
                )
            ),
            "usage": to_float(
                get_value(
                    record,
                    "usageReturningReceiving",
                    "usage_returning_receiving",
                )
            ),
            "ppa": to_float(
                get_value(
                    record,
                    "ppaReturningReceiving",
                    "ppa_returning_receiving",
                )
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

    # Diagnostic output.
    # This lets us immediately know whether the API fields
    # were successfully mapped instead of silently producing
    # a file full of zeros.

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
            f"{min(nonzero_overall):.2f}"
        )

        print(
            f"Maximum overall returning production: "
            f"{max(nonzero_overall):.2f}"
        )

        print(
            f"Average overall returning production: "
            f"{sum(nonzero_overall) / len(nonzero_overall):.2f}"
        )

    else:
        print(
            "WARNING: No non-zero returning production values "
            "were found."
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
