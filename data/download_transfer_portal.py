"""
Download college football transfer portal data.

The portal data will be used to build the 2026 roster/talent
adjustment layer.
"""

import json
import sys
from pathlib import Path

from data.cfbd_api import client


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "raw" / "transfer_portal"


def download_transfer_portal(year):
    """Download transfer portal data for a season."""

    portal_records = client.get(
        "/player/portal",
        params={"year": year},
    )

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIRECTORY / f"{year}.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(portal_records, file, indent=4)

    print(
        f"Downloaded {len(portal_records)} "
        f"transfer portal records for {year}."
    )
    print(f"Saved to {output_file}")

    if portal_records:
        print()
        print("First raw CFBD transfer record:")
        print(json.dumps(portal_records[0], indent=4))


if __name__ == "__main__":
    year = 2025

    if len(sys.argv) > 1:
        year = int(sys.argv[1])

    download_transfer_portal(year)
