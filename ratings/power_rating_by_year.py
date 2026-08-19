"""Run the existing Project Gridiron power-rating formula for any season.

Usage:
    python -m ratings.power_rating_by_year 2023

This intentionally reuses ratings.power_rating.calculate_power_ratings so the
historical baseline is formula-identical to the existing 2025 implementation.
The legacy module is path/year-hardcoded, so this runner redirects its file
paths for the requested year and corrects the emitted season field afterward.
"""

import json
import sys
from pathlib import Path

from ratings import power_rating as legacy


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run(year):
    processed = PROJECT_ROOT / "data" / "processed"

    legacy.STRENGTH_FILE = processed / f"team_strength_{year}.json"
    legacy.RESULTS_FILE = processed / f"team_results_{year}.json"
    legacy.SOS_FILE = processed / f"strength_of_schedule_{year}.json"
    legacy.OUTPUT_FILE = processed / f"power_ratings_{year}.json"

    for path in (legacy.STRENGTH_FILE, legacy.RESULTS_FILE, legacy.SOS_FILE):
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    legacy.calculate_power_ratings()

    with legacy.OUTPUT_FILE.open("r", encoding="utf-8") as file:
        ratings = json.load(file)

    for record in ratings:
        record["season"] = year

    with legacy.OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(ratings, file, indent=4)

    print(f"Corrected season metadata to {year} for {len(ratings)} ratings.")
    print(f"Historical power ratings ready: {legacy.OUTPUT_FILE}")


if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    run(year)
