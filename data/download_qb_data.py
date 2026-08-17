"""
Download quarterback continuity / quality data from CFBD.

This is a diagnostic downloader for building a QB continuity model.

It collects:
- Player usage
- Player season overview
- Player season PPA
- Team roster data

for the requested season.

Usage:
    python -m data.download_qb_data 2024
    python -m data.download_qb_data 2025

The first goal is to inspect the raw schemas and determine which
fields can reliably measure:
- returning starter status
- passing usage
- prior production
- prior efficiency
- QB experience

This module does NOT modify any ratings.
"""

import json
import os
import sys
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent

BASE_URL = "https://api.collegefootballdata.com"

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "qb_data"
)


def get_api_key():
    """Return CFBD API key from environment."""

    api_key = os.getenv(
        "CFBD_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "CFBD_API_KEY environment variable is not set."
        )

    return api_key


def api_get(
    endpoint,
    params
):
    """Run one authenticated CFBD GET request."""

    headers = {
        "Authorization":
            f"Bearer {get_api_key()}"
    }

    response = requests.get(
        f"{BASE_URL}{endpoint}",
        headers=headers,
        params=params,
        timeout=60,
    )

    print(
        f"GET {endpoint}"
    )

    print(
        f"Status code: "
        f"{response.status_code}"
    )

    response.raise_for_status()

    return response.json()


def save_json(
    data,
    path
):
    """Save JSON output."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4
        )


def print_first_record(
    title,
    records
):
    """Print first raw record and field names."""

    print()

    print("=" * 72)

    print(
        title
    )

    print("=" * 72)

    print(
        f"Records returned: "
        f"{len(records)}"
    )

    if not records:
        return

    print()

    print(
        "FIRST RECORD"
    )

    print("-" * 72)

    print(
        json.dumps(
            records[0],
            indent=4
        )
    )

    print()

    print(
        "FIELDS"
    )

    print("-" * 72)

    if isinstance(
        records[0],
        dict
    ):

        for key in sorted(
            records[0].keys()
        ):
            print(
                key
            )


def quarterback_filter(records):
    """
    Keep QB records where position is exposed.

    Some endpoints may not include position. Those records are
    preserved separately in the raw files.
    """

    quarterbacks = []

    for record in records:

        position = (
            record.get(
                "position"
            )
            or ""
        )

        if (
            str(position)
            .strip()
            .upper()
            in {
                "QB",
                "QUARTERBACK",
            }
        ):

            quarterbacks.append(
                record
            )

    return quarterbacks


def download_qb_data(year):
    """Download diagnostic QB-related data for one season."""

    print("=" * 72)

    print(
        f"CFBD QB DATA DIAGNOSTIC - {year}"
    )

    print("=" * 72)

    print()

    # ------------------------------------------------------------
    # PLAYER USAGE
    # ------------------------------------------------------------

    usage = api_get(
        "/player/usage",
        {
            "year": year,
        }
    )

    save_json(
        usage,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "player_usage.json"
        )
    )

    print_first_record(
        "PLAYER USAGE",
        usage
    )

    usage_qbs = quarterback_filter(
        usage
    )

    print(
        f"QB usage records identified: "
        f"{len(usage_qbs)}"
    )

    save_json(
        usage_qbs,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "player_usage_qbs.json"
        )
    )

    # ------------------------------------------------------------
    # PLAYER SEASON OVERVIEW
    # ------------------------------------------------------------

    overview = api_get(
        "/player/season/overview",
        {
            "year": year,
        }
    )

    save_json(
        overview,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "season_overview.json"
        )
    )

    print_first_record(
        "PLAYER SEASON OVERVIEW",
        overview
    )

    overview_qbs = quarterback_filter(
        overview
    )

    print(
        f"QB overview records identified: "
        f"{len(overview_qbs)}"
    )

    save_json(
        overview_qbs,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "season_overview_qbs.json"
        )
    )

    # ------------------------------------------------------------
    # PLAYER SEASON PPA
    # ------------------------------------------------------------

    ppa = api_get(
        "/ppa/players/season",
        {
            "year": year,
        }
    )

    save_json(
        ppa,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "player_ppa.json"
        )
    )

    print_first_record(
        "PLAYER SEASON PPA",
        ppa
    )

    ppa_qbs = quarterback_filter(
        ppa
    )

    print(
        f"QB PPA records identified: "
        f"{len(ppa_qbs)}"
    )

    save_json(
        ppa_qbs,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "player_ppa_qbs.json"
        )
    )

    # ------------------------------------------------------------
    # ROSTERS
    # ------------------------------------------------------------

    roster = api_get(
        "/roster",
        {
            "year": year,
        }
    )

    save_json(
        roster,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "roster.json"
        )
    )

    print_first_record(
        "TEAM ROSTER",
        roster
    )

    roster_qbs = quarterback_filter(
        roster
    )

    print(
        f"QB roster records identified: "
        f"{len(roster_qbs)}"
    )

    save_json(
        roster_qbs,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "roster_qbs.json"
        )
    )

    # ------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------

    print()

    print("=" * 72)

    print(
        "QB DATA DOWNLOAD SUMMARY"
    )

    print("=" * 72)

    print(
        f"Season: "
        f"{year}"
    )

    print(
        f"Usage records: "
        f"{len(usage)}"
    )

    print(
        f"QB usage records: "
        f"{len(usage_qbs)}"
    )

    print(
        f"Overview records: "
        f"{len(overview)}"
    )

    print(
        f"QB overview records: "
        f"{len(overview_qbs)}"
    )

    print(
        f"PPA records: "
        f"{len(ppa)}"
    )

    print(
        f"QB PPA records: "
        f"{len(ppa_qbs)}"
    )

    print(
        f"Roster records: "
        f"{len(roster)}"
    )

    print(
        f"QB roster records: "
        f"{len(roster_qbs)}"
    )

    print()

    print(
        "Saved under:"
    )

    print(
        OUTPUT_DIRECTORY
        / str(year)
    )


if __name__ == "__main__":

    year = 2025

    if len(sys.argv) > 1:

        year = int(
            sys.argv[1]
        )

    download_qb_data(
        year
    )
