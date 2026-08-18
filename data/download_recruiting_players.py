"""
Download historical player recruiting ratings from CFBD.

These records will be used to estimate the talent level of
players who later enter or leave through the transfer portal.
"""

import json
import sys
from pathlib import Path

from data.cfbd_api import client


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "raw" / "recruiting_players"


def download_recruiting_class(year):
    """Download one recruiting class."""

    records = client.get(
        "/recruiting/players",
        params={"year": year},
    )

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIRECTORY / f"{year}.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=4)

    print(f"Downloaded {len(records)} recruiting records for {year}.")
    print(f"Saved to {output_file}")
    return records


def download_recruiting_history(start_year, end_year):
    """Download a range of recruiting classes."""

    print("=" * 60)
    print("CFBD PLAYER RECRUITING HISTORY")
    print("=" * 60)
    print(f"Downloading recruiting classes {start_year} through {end_year}.")
    print()

    total_records = 0
    first_record = None

    for year in range(start_year, end_year + 1):
        records = download_recruiting_class(year)
        total_records += len(records)
        if first_record is None and records:
            first_record = records[0]

    print()
    print(f"Total recruiting records downloaded: {total_records}")

    if first_record:
        print()
        print("FIRST RAW CFBD RECRUITING RECORD")
        print("-" * 60)
        print(json.dumps(first_record, indent=4))
        print()
        print("FIELDS")
        print("-" * 60)
        for key in sorted(first_record.keys()):
            print(key)


if __name__ == "__main__":
    start_year = 2019
    end_year = 2025

    if len(sys.argv) > 1:
        start_year = int(sys.argv[1])
    if len(sys.argv) > 2:
        end_year = int(sys.argv[2])

    download_recruiting_history(start_year, end_year)
