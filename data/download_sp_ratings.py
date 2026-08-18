"""
Download historical SP+ ratings from CFBD.

These ratings will be used as a secondary team-strength baseline
alongside Project Gridiron's own power ratings.
"""

import json
import sys
from pathlib import Path

from data.cfbd_api import client


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "raw" / "sp_ratings"


def download_sp_ratings(year):
    """Download SP+ ratings for one season."""

    records = client.get(
        "/ratings/sp",
        params={"year": year},
    )

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIRECTORY / f"{year}.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=4)

    print(f"Downloaded {len(records)} SP+ ratings for {year}.")
    print(f"Saved to {output_file}")
    return records


def download_sp_history(start_year, end_year):
    """Download SP+ ratings for a range of seasons."""

    print("=" * 70)
    print("CFBD SP+ RATINGS")
    print("=" * 70)
    print(f"Downloading SP+ ratings {start_year} through {end_year}.")
    print()

    total_records = 0
    first_record = None

    for year in range(start_year, end_year + 1):
        records = download_sp_ratings(year)
        total_records += len(records)
        if first_record is None and records:
            first_record = records[0]

    print()
    print(f"Total SP+ records downloaded: {total_records}")

    if first_record:
        print()
        print("FIRST RAW CFBD SP+ RECORD")
        print("-" * 70)
        print(json.dumps(first_record, indent=4))
        print()
        print("FIELDS")
        print("-" * 70)
        for key in sorted(first_record.keys()):
            print(key)


if __name__ == "__main__":
    start_year = 2024
    end_year = 2025

    if len(sys.argv) > 1:
        start_year = int(sys.argv[1])
    if len(sys.argv) > 2:
        end_year = int(sys.argv[2])

    download_sp_history(start_year, end_year)
