"""
Project Gridiron
Coaching Data Downloader

Downloads historical head-coaching data from CFBD.

Usage:
    python -m data.download_coaching_data 2024
    python -m data.download_coaching_data 2025
    python -m data.download_coaching_data 2026

Outputs:
    data/raw/coaching/<year>/coaches.json
    data/raw/coaching/<year>/coach_seasons.json
    data/raw/coaching/<year>/coach_tenures.json

Primary goals:

- identify each team's head coach
- determine whether the head coach returned the following season
- measure head-coach tenure
- identify first-year / second-year coaches
- preserve coach season record and historical context
- support later 2024 -> 2025 validation

CFBD currently exposes:
    GET /coaches
    GET /coaches/seasons
    GET /coaches/tenures

This module is diagnostic only and does NOT modify ratings.
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
    / "coaching"
)


def get_api_key():
    """Return CFBD API key."""

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
    Run authenticated CFBD GET request.

    Optional requests return an empty list on failure.
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

        print("-" * 76)

        try:

            print(
                json.dumps(
                    response.json(),
                    indent=4
                )
            )

        except ValueError:

            print(
                response.text[:3000]
            )

        if required:

            response.raise_for_status()

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
                f"Invalid JSON returned by {endpoint}"
            ) from error

        return []

    if not isinstance(
        data,
        list
    ):

        print(
            f"Unexpected response type from "
            f"{endpoint}: "
            f"{type(data).__name__}"
        )

        if required:

            raise ValueError(
                f"Expected list response from {endpoint}"
            )

        return []

    return data


def save_json(
    data,
    path
):
    """Save JSON."""

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


def print_dataset(
    title,
    records
):
    """Print diagnostic schema."""

    print()

    print("=" * 76)

    print(
        title
    )

    print("=" * 76)

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

    print("-" * 76)

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

    print("-" * 76)

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


def download_coaches(year):
    """
    Download historical head-coach records for a season.

    CFBD supports year filtering directly.
    """

    records = api_get(
        "/coaches",
        {
            "year": year,
        },
        required=True,
    )

    path = (
        OUTPUT_DIRECTORY
        / str(year)
        / "coaches.json"
    )

    save_json(
        records,
        path
    )

    print_dataset(
        "COACHES",
        records
    )

    return records


def download_coach_seasons(year):
    """
    Download detailed coach-season records.

    These contain season-specific results and team context.
    """

    records = api_get(
        "/coaches/seasons",
        {
            "year": year,
        },
        required=True,
    )

    path = (
        OUTPUT_DIRECTORY
        / str(year)
        / "coach_seasons.json"
    )

    save_json(
        records,
        path
    )

    print_dataset(
        "COACH SEASONS",
        records
    )

    return records


def download_coach_tenures(year):
    """
    Download coaching tenures containing the requested season.

    CFBD defines the year parameter here as:
        season year contained within the tenure.
    """

    records = api_get(
        "/coaches/tenures",
        {
            "year": year,
        },
        required=True,
    )

    path = (
        OUTPUT_DIRECTORY
        / str(year)
        / "coach_tenures.json"
    )

    save_json(
        records,
        path
    )

    print_dataset(
        "COACH TENURES",
        records
    )

    return records


def extract_team(record):
    """
    Attempt to extract team name across possible CFBD schemas.

    This is only used for diagnostic counting.
    """

    team = record.get(
        "team"
    )

    if isinstance(
        team,
        str
    ):

        return team

    if isinstance(
        team,
        dict
    ):

        return (
            team.get(
                "school"
            )
            or
            team.get(
                "name"
            )
        )

    teams = record.get(
        "teams"
    )

    if isinstance(
        teams,
        list
    ) and teams:

        first = teams[0]

        if isinstance(
            first,
            str
        ):

            return first

        if isinstance(
            first,
            dict
        ):

            return (
                first.get(
                    "school"
                )
                or
                first.get(
                    "name"
                )
            )

    return None


def summarize_unique_teams(records):
    """Count unique team names in dataset."""

    teams = set()

    for record in records:

        team = extract_team(
            record
        )

        if team:

            teams.add(
                team
            )

    return len(
        teams
    )


def download_coaching_data(year):
    """Download all coaching datasets for one season."""

    print("=" * 76)

    print(
        f"CFBD COACHING DATA DIAGNOSTIC - {year}"
    )

    print("=" * 76)

    coaches = download_coaches(
        year
    )

    coach_seasons = download_coach_seasons(
        year
    )

    coach_tenures = download_coach_tenures(
        year
    )

    print()

    print("=" * 76)

    print(
        "COACHING DATA DOWNLOAD SUMMARY"
    )

    print("=" * 76)

    print(
        f"Season: "
        f"{year}"
    )

    print()

    print(
        f"Coach records: "
        f"{len(coaches)}"
    )

    print(
        f"Coach-season records: "
        f"{len(coach_seasons)}"
    )

    print(
        f"Coach-tenure records: "
        f"{len(coach_tenures)}"
    )

    print()

    print(
        f"Teams identifiable in coaches: "
        f"{summarize_unique_teams(coaches)}"
    )

    print(
        f"Teams identifiable in coach seasons: "
        f"{summarize_unique_teams(coach_seasons)}"
    )

    print(
        f"Teams identifiable in coach tenures: "
        f"{summarize_unique_teams(coach_tenures)}"
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

    year = 2024

    if len(sys.argv) > 1:

        year = int(
            sys.argv[1]
        )

    download_coaching_data(
        year
    )
