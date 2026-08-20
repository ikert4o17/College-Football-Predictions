"""
Process returning-production data into model-ready team profiles.

Historical CFBD data uses PPA-based returning-production fields. Beginning
with the 2026 raw data, the source schema can instead provide returning snaps
and returning_snap_percent. Both schemas are normalized to the same model
field: overall.percent on a 0-1 scale.

Usage:
    python -m data.process_returning_production 2025
    python -m data.process_returning_production 2026
"""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def input_file(year):
    return PROJECT_ROOT / "data" / "raw" / "returning_production" / f"{year}.json"


def output_file(year):
    return PROJECT_ROOT / "data" / "processed" / f"returning_production_{year}.json"


def safe_float(value):
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def detect_schema(record):
    """Identify the returning-production schema used by one raw record."""
    if "percentPPA" in record:
        return "ppa"
    if "returning_snap_percent" in record:
        return "snaps"
    return "unknown"


def process_team(record):
    """Convert one raw record into the standardized team profile."""
    schema = detect_schema(record)

    if schema == "ppa":
        return {
            "season": record.get("season"),
            "team": record.get("team"),
            "conference": record.get("conference"),
            "source_schema": "ppa",
            "overall": {
                "percent": safe_float(record.get("percentPPA")),
                "usage": safe_float(record.get("usage")),
                "ppa": safe_float(record.get("totalPPA")),
            },
            "passing": {
                "percent": safe_float(record.get("percentPassingPPA")),
                "usage": safe_float(record.get("passingUsage")),
                "ppa": safe_float(record.get("totalPassingPPA")),
            },
            "rushing": {
                "percent": safe_float(record.get("percentRushingPPA")),
                "usage": safe_float(record.get("rushingUsage")),
                "ppa": safe_float(record.get("totalRushingPPA")),
            },
            "receiving": {
                "percent": safe_float(record.get("percentReceivingPPA")),
                "usage": safe_float(record.get("receivingUsage")),
                "ppa": safe_float(record.get("totalReceivingPPA")),
            },
        }

    if schema == "snaps":
        snap_percent = safe_float(record.get("returning_snap_percent")) / 100.0
        return {
            "season": record.get("season"),
            "team": record.get("team"),
            "conference": record.get("conference"),
            "source_schema": "snaps",
            "source": record.get("source"),
            "rank_by_returning_snaps": record.get("rank_by_returning_snaps"),
            "returning_snaps": safe_float(record.get("returning_snaps")),
            "overall": {
                "percent": snap_percent,
                "usage": 0.0,
                "ppa": 0.0,
            },
            "passing": {"percent": 0.0, "usage": 0.0, "ppa": 0.0},
            "rushing": {"percent": 0.0, "usage": 0.0, "ppa": 0.0},
            "receiving": {"percent": 0.0, "usage": 0.0, "ppa": 0.0},
        }

    raise ValueError(
        f"Unrecognized returning-production schema for team {record.get('team')!r}. "
        f"Fields: {sorted(record.keys())}"
    )


def process_returning_production(year):
    source = input_file(year)
    destination = output_file(year)

    if not source.exists():
        raise FileNotFoundError(f"Returning production input file not found: {source}")

    with source.open("r", encoding="utf-8") as file:
        raw_records = json.load(file)

    processed = []
    schema_counts = {}

    for record in raw_records:
        schema = detect_schema(record)
        schema_counts[schema] = schema_counts.get(schema, 0) + 1
        team = process_team(record)
        if team["team"]:
            processed.append(team)

    processed.sort(key=lambda team: team["team"])
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8") as file:
        json.dump(processed, file, indent=4)

    values = [team["overall"]["percent"] for team in processed]
    non_zero = [value for value in values if value > 0]

    print("=" * 70)
    print(f"{year} RETURNING PRODUCTION PROCESSING")
    print("=" * 70)
    print(f"Processed {len(processed)} returning production profiles.")
    print(f"Saved to {destination}")
    print()
    print("SOURCE SCHEMAS")
    print("-" * 70)
    for schema, count in sorted(schema_counts.items()):
        print(f"{schema}: {count}")
    print()
    print(f"Teams with non-zero overall returning production: {len(non_zero)}")

    if values:
        print(f"Minimum overall returning production: {min(values):.3f}")
        print(f"Maximum overall returning production: {max(values):.3f}")
        print(f"Average overall returning production: {sum(values) / len(values):.3f}")

    print()
    print("TOP 10 RETURNING PRODUCTION")
    print("-" * 70)
    highest = sorted(processed, key=lambda team: team["overall"]["percent"], reverse=True)
    for team in highest[:10]:
        print(f"{team['team']}: {team['overall']['percent']:.3f}")


if __name__ == "__main__":
    year = 2025
    if len(sys.argv) > 1:
        year = int(sys.argv[1])
    process_returning_production(year)
