"""
Project Gridiron
Coaching Data Downloader

Downloads historical head-coaching data from CFBD through the shared
Project Gridiron client.
"""

import json
import sys
from pathlib import Path

from data.cfbd_api import client


PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "coaching"
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


def api_get(endpoint, params, required=True):
    """
    Fetch a CFBD list through the shared client.

    Required endpoints raise on failure. Optional endpoint failures return
    an empty list, except quota/request-budget guard failures, which always
    propagate so protection cannot be bypassed accidentally.
    """

    print()
    print(f"GET {endpoint}")
    print(f"Parameters: {params}")

    try:
        data = client.get(endpoint, params=params)
    except (RuntimeError, ValueError) as error:
        if required or _is_guard_error(error):
            raise

        print()
        print(f"Skipping optional endpoint: {endpoint}")
        print(f"Reason: {error}")
        return []

    if not isinstance(data, list):
        if required:
            raise ValueError(f"Expected list response from {endpoint}")

        print()
        print(
            f"Unexpected response type from {endpoint}: "
            f"{type(data).__name__}. Skipping."
        )
        return []

    return data


def save_json(data, path):
    """Save JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def print_dataset(title, records):
    """Print diagnostic schema."""

    print()
    print("=" * 76)
    print(title)
    print("=" * 76)
    print(f"Records returned: {len(records)}")

    if not records:
        print("No records available.")
        return

    print()
    print("FIRST RECORD")
    print("-" * 76)
    print(json.dumps(records[0], indent=4))
    print()
    print("FIELDS")
    print("-" * 76)

    if isinstance(records[0], dict):
        for key in sorted(records[0].keys()):
            print(key)


def download_coaches(year):
    """Download historical head-coach records for a season."""

    records = api_get("/coaches", {"year": year}, required=True)
    path = OUTPUT_DIRECTORY / str(year) / "coaches.json"
    save_json(records, path)
    print_dataset("COACHES", records)
    return records


def download_coach_seasons(year):
    """Download detailed coach-season records."""

    records = api_get("/coaches/seasons", {"year": year}, required=True)
    path = OUTPUT_DIRECTORY / str(year) / "coach_seasons.json"
    save_json(records, path)
    print_dataset("COACH SEASONS", records)
    return records


def download_coach_tenures(year):
    """Attempt the optional year-only tenure request."""

    records = api_get("/coaches/tenures", {"year": year}, required=False)
    path = OUTPUT_DIRECTORY / str(year) / "coach_tenures.json"
    save_json(records, path)
    print_dataset("COACH TENURES", records)
    return records


def extract_team_from_coach_record(record):
    """Extract team from /coaches response."""

    seasons = record.get("seasons")

    if isinstance(seasons, list) and seasons:
        latest = seasons[-1]
        if isinstance(latest, dict):
            return latest.get("school")

    return None


def extract_team_from_season_record(record):
    """Extract team from /coaches/seasons response."""

    team = record.get("team")

    if isinstance(team, dict):
        return team.get("school") or team.get("name")

    if isinstance(team, str):
        return team

    return None


def extract_team_from_tenure_record(record):
    """Extract team from tenure response where available."""

    team = record.get("team")

    if isinstance(team, dict):
        return team.get("school") or team.get("name")

    if isinstance(team, str):
        return team

    return None


def summarize_unique_teams(records, extractor):
    """Count unique team names."""

    teams = set()

    for record in records:
        team = extractor(record)
        if team:
            teams.add(team)

    return len(teams)


def summarize_coach_ids(records):
    """Count unique coach IDs in season records."""

    ids = set()

    for record in records:
        coach = record.get("coach")
        if not isinstance(coach, dict):
            continue

        coach_id = coach.get("id")
        if coach_id is not None:
            ids.add(coach_id)

    return len(ids)


def download_coaching_data(year):
    """Download all coaching datasets for one season."""

    print("=" * 76)
    print(f"CFBD COACHING DATA DIAGNOSTIC - {year}")
    print("=" * 76)

    coaches = download_coaches(year)
    coach_seasons = download_coach_seasons(year)
    coach_tenures = download_coach_tenures(year)

    print()
    print("=" * 76)
    print("COACHING DATA DOWNLOAD SUMMARY")
    print("=" * 76)
    print(f"Season: {year}")
    print()
    print(f"Coach records: {len(coaches)}")
    print(f"Coach-season records: {len(coach_seasons)}")
    print(f"Coach-tenure records: {len(coach_tenures)}")
    print()
    print(f"Unique coaches in season data: {summarize_coach_ids(coach_seasons)}")
    print()
    print(
        "Teams identifiable in coaches: "
        f"{summarize_unique_teams(coaches, extract_team_from_coach_record)}"
    )
    print(
        "Teams identifiable in coach seasons: "
        f"{summarize_unique_teams(coach_seasons, extract_team_from_season_record)}"
    )
    print(
        "Teams identifiable in coach tenures: "
        f"{summarize_unique_teams(coach_tenures, extract_team_from_tenure_record)}"
    )
    print()

    if not coach_tenures:
        print("NOTE:")
        print("Coach tenure data was unavailable from a year-only request.")
        print("Continuity will be derived from coach-season records instead.")
        print()

    print("Saved under:")
    print(OUTPUT_DIRECTORY / str(year))


if __name__ == "__main__":
    year = 2024

    if len(sys.argv) > 1:
        year = int(sys.argv[1])

    download_coaching_data(year)
