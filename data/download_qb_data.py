"""
Download quarterback continuity / quality data from CFBD.

This is a diagnostic downloader for building a QB continuity model.

It collects:
- Player usage
- Player season overview, when available
- Player season PPA
- Team roster data

Usage:
    python -m data.download_qb_data 2024
    python -m data.download_qb_data 2025

IMPORTANT:
Some CFBD endpoints may require additional filters.
A failed optional endpoint will NOT terminate this diagnostic run.

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
    params,
    required=True
):
    """
    Run one authenticated CFBD GET request.

    Required endpoints raise on failure.
    Optional endpoints return an empty list.
    """

    headers = {
        "Authorization":
            f"Bearer {get_api_key()}"
    }

    print()

    print(
        f"GET {endpoint}"
    )

    print(
        f"Parameters: {params}"
    )

    response = requests.get(
        f"{BASE_URL}{endpoint}",
        headers=headers,
        params=params,
        timeout=60,
    )

    print(
        f"Status code: "
        f"{response.status_code}"
    )

    if response.status_code >= 400:

        print()

        print(
            "ERROR RESPONSE"
        )

        print("-" * 72)

        try:

            error_data = response.json()

            print(
                json.dumps(
                    error_data,
                    indent=4
                )
            )

        except ValueError:

            print(
                response.text[:3000]
            )

        if required:

            response.raise_for_status()

        print()

        print(
            f"Skipping optional endpoint: "
            f"{endpoint}"
        )

        return []

    try:

        data = response.json()

    except ValueError as error:

        if required:

            raise ValueError(
                f"CFBD returned invalid JSON for "
                f"{endpoint}"
            ) from error

        print(
            f"Invalid JSON returned by optional endpoint "
            f"{endpoint}. Skipping."
        )

        return []

    if isinstance(
        data,
        list
    ):

        return data

    print(
        f"Unexpected response structure from "
        f"{endpoint}: "
        f"{type(data).__name__}"
    )

    if required:

        raise ValueError(
            f"Expected list response from {endpoint}."
        )

    return []


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

        print(
            "No records available."
        )

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
    """Keep records explicitly identified as quarterbacks."""

    quarterbacks = []

    for record in records:

        if not isinstance(
            record,
            dict
        ):
            continue

        position = (
            record.get(
                "position"
            )
            or ""
        )

        normalized = (
            str(position)
            .strip()
            .upper()
        )

        if normalized in {
            "QB",
            "QUARTERBACK",
        }:

            quarterbacks.append(
                record
            )

    return quarterbacks


def download_usage(year):
    """Download player usage."""

    records = api_get(
        "/player/usage",
        {
            "year": year,
        },
        required=True,
    )

    save_json(
        records,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "player_usage.json"
        )
    )

    print_first_record(
        "PLAYER USAGE",
        records
    )

    quarterbacks = quarterback_filter(
        records
    )

    print()

    print(
        f"QB usage records identified: "
        f"{len(quarterbacks)}"
    )

    save_json(
        quarterbacks,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "player_usage_qbs.json"
        )
    )

    return (
        records,
        quarterbacks,
    )


def download_overview(year):
    """
    Attempt to download player season overview.

    This endpoint is optional because CFBD may require filters
    beyond season/year.
    """

    records = api_get(
        "/player/season/overview",
        {
            "year": year,
        },
        required=False,
    )

    save_json(
        records,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "season_overview.json"
        )
    )

    print_first_record(
        "PLAYER SEASON OVERVIEW",
        records
    )

    quarterbacks = quarterback_filter(
        records
    )

    print()

    print(
        f"QB overview records identified: "
        f"{len(quarterbacks)}"
    )

    save_json(
        quarterbacks,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "season_overview_qbs.json"
        )
    )

    return (
        records,
        quarterbacks,
    )


def download_ppa(year):
    """Download player-season PPA data."""

    records = api_get(
        "/ppa/players/season",
        {
            "year": year,
        },
        required=False,
    )

    save_json(
        records,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "player_ppa.json"
        )
    )

    print_first_record(
        "PLAYER SEASON PPA",
        records
    )

    quarterbacks = quarterback_filter(
        records
    )

    print()

    print(
        f"QB PPA records identified: "
        f"{len(quarterbacks)}"
    )

    save_json(
        quarterbacks,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "player_ppa_qbs.json"
        )
    )

    return (
        records,
        quarterbacks,
    )


def download_roster(year):
    """Download roster data."""

    records = api_get(
        "/roster",
        {
            "year": year,
        },
        required=False,
    )

    save_json(
        records,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "roster.json"
        )
    )

    print_first_record(
        "TEAM ROSTER",
        records
    )

    quarterbacks = quarterback_filter(
        records
    )

    print()

    print(
        f"QB roster records identified: "
        f"{len(quarterbacks)}"
    )

    save_json(
        quarterbacks,
        (
            OUTPUT_DIRECTORY
            / str(year)
            / "roster_qbs.json"
        )
    )

    return (
        records,
        quarterbacks,
    )


def download_qb_data(year):
    """Download all QB diagnostic datasets for one season."""

    print("=" * 72)

    print(
        f"CFBD QB DATA DIAGNOSTIC - {year}"
    )

    print("=" * 72)

    (
        usage,
        usage_qbs,
    ) = download_usage(
        year
    )

    (
        overview,
        overview_qbs,
    ) = download_overview(
        year
    )

    (
        ppa,
        ppa_qbs,
    ) = download_ppa(
        year
    )

    (
        roster,
        roster_qbs,
    ) = download_roster(
        year
    )

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

    print()

    print(
        f"Usage records: "
        f"{len(usage)}"
    )

    print(
        f"QB usage records: "
        f"{len(usage_qbs)}"
    )

    print()

    print(
        f"Overview records: "
        f"{len(overview)}"
    )

    print(
        f"QB overview records: "
        f"{len(overview_qbs)}"
    )

    print()

    print(
        f"PPA records: "
        f"{len(ppa)}"
    )

    print(
        f"QB PPA records: "
        f"{len(ppa_qbs)}"
    )

    print()

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

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "A zero count for an optional endpoint does not "
        "necessarily mean the data does not exist."
    )

    print(
        "Check the printed HTTP response to determine whether "
        "CFBD requires additional filters."
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
