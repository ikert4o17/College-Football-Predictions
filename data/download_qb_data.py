"""
Download quarterback continuity / quality data from CFBD through the
shared Project Gridiron client.
"""

import json
import sys
from pathlib import Path

from requests.exceptions import RequestException

from data.cfbd_api import client


PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "qb_data"
)


def _is_guard_error(error):
    """Return whether an error represents quota/request-budget protection."""

    message = str(error).lower()

    return (
        "quota" in message
        or "request budget" in message
        or "request-budget" in message
        or "max calls" in message
    )


def fetch_records(endpoint, params, required=True):
    """
    Fetch a CFBD list through the shared client.

    Optional endpoint failures return an empty list, while quota and
    request-budget protection always propagate.
    """

    print()
    print(f"GET {endpoint}")
    print(f"Parameters: {params}")

    try:
        data = client.get(endpoint, params=params)
    except (RuntimeError, ValueError, RequestException) as error:
        if required or _is_guard_error(error):
            raise

        print()
        print(f"Skipping optional endpoint: {endpoint}")
        print(f"Reason: {error}")
        return []

    if isinstance(data, list):
        return data

    if required:
        raise ValueError(f"Expected list response from {endpoint}.")

    print(
        f"Unexpected response structure from {endpoint}: "
        f"{type(data).__name__}. Skipping."
    )
    return []


def save_json(data, path):
    """Save JSON output."""

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def print_first_record(title, records):
    """Print first raw record and field names."""

    print()
    print("=" * 72)
    print(title)
    print("=" * 72)
    print(f"Records returned: {len(records)}")

    if not records:
        print("No records available.")
        return

    print()
    print("FIRST RECORD")
    print("-" * 72)
    print(json.dumps(records[0], indent=4))
    print()
    print("FIELDS")
    print("-" * 72)

    if isinstance(records[0], dict):
        for key in sorted(records[0].keys()):
            print(key)


def quarterback_filter(records):
    """Keep records explicitly identified as quarterbacks."""

    quarterbacks = []

    for record in records:
        if not isinstance(record, dict):
            continue

        position = record.get("position") or ""
        normalized = str(position).strip().upper()

        if normalized in {"QB", "QUARTERBACK"}:
            quarterbacks.append(record)

    return quarterbacks


def _save_dataset(year, filename, title, records):
    """Save a dataset plus its quarterback-only subset."""

    base = OUTPUT_DIRECTORY / str(year)
    save_json(records, base / f"{filename}.json")
    print_first_record(title, records)

    quarterbacks = quarterback_filter(records)

    print()
    print(f"QB {filename.replace('_', ' ')} records identified: {len(quarterbacks)}")

    save_json(quarterbacks, base / f"{filename}_qbs.json")
    return records, quarterbacks


def download_usage(year):
    """Download player usage."""

    records = fetch_records("/player/usage", {"year": year}, required=True)
    return _save_dataset(year, "player_usage", "PLAYER USAGE", records)


def download_overview(year):
    """Attempt to download optional player season overview data."""

    records = fetch_records(
        "/player/season/overview",
        {"year": year},
        required=False,
    )
    return _save_dataset(
        year,
        "season_overview",
        "PLAYER SEASON OVERVIEW",
        records,
    )


def download_ppa(year):
    """Download optional player-season PPA data."""

    records = fetch_records(
        "/ppa/players/season",
        {"year": year},
        required=False,
    )
    return _save_dataset(year, "player_ppa", "PLAYER SEASON PPA", records)


def download_roster(year):
    """Download optional roster data."""

    records = fetch_records("/roster", {"year": year}, required=False)
    return _save_dataset(year, "roster", "TEAM ROSTER", records)


def download_qb_data(year):
    """Download all QB diagnostic datasets for one season."""

    print("=" * 72)
    print(f"CFBD QB DATA DIAGNOSTIC - {year}")
    print("=" * 72)

    usage, usage_qbs = download_usage(year)
    overview, overview_qbs = download_overview(year)
    ppa, ppa_qbs = download_ppa(year)
    roster, roster_qbs = download_roster(year)

    print()
    print("=" * 72)
    print("QB DATA DOWNLOAD SUMMARY")
    print("=" * 72)
    print(f"Season: {year}")
    print()
    print(f"Usage records: {len(usage)}")
    print(f"QB usage records: {len(usage_qbs)}")
    print()
    print(f"Overview records: {len(overview)}")
    print(f"QB overview records: {len(overview_qbs)}")
    print()
    print(f"PPA records: {len(ppa)}")
    print(f"QB PPA records: {len(ppa_qbs)}")
    print()
    print(f"Roster records: {len(roster)}")
    print(f"QB roster records: {len(roster_qbs)}")
    print()
    print("Saved under:")
    print(OUTPUT_DIRECTORY / str(year))
    print()
    print("IMPORTANT:")
    print(
        "A zero count for an optional endpoint does not necessarily mean "
        "the data does not exist."
    )
    print("CFBD may require additional filters for that endpoint.")


if __name__ == "__main__":
    year = 2025

    if len(sys.argv) > 1:
        year = int(sys.argv[1])

    download_qb_data(year)
