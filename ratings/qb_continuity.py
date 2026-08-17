"""
Project Gridiron
QB Continuity Processor

Build team-level quarterback continuity metrics for a target season.

Historical example:
    2024 QB data -> 2025 roster status

Usage:
    python -m ratings.qb_continuity 2025

Inputs:
    data/raw/qb_data/2024/player_usage_qbs.json
    data/raw/qb_data/2024/player_ppa_qbs.json
    data/raw/qb_data/2024/roster_qbs.json
    data/raw/qb_data/2025/roster_qbs.json

Output:
    data/processed/qb_continuity_2025.json

Primary QB selection:
    highest passing usage on each team

This module does NOT modify the production power ratings.
"""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def season_directory(year):
    """Return QB raw-data directory for a season."""

    return (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "qb_data"
        / str(year)
    )


def output_file(year):
    """Return processed QB continuity output path."""

    return (
        PROJECT_ROOT
        / "data"
        / "processed"
        / f"qb_continuity_{year}.json"
    )


def load_json(path):
    """Load JSON file."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def safe_float(value):
    """Safely convert value to float."""

    if value is None:
        return 0.0

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return 0.0


def normalize_player_id(value):
    """Normalize CFBD player ID for joining datasets."""

    if value is None:
        return None

    return str(value).strip()


def build_player_lookup(records):
    """Build player-ID lookup."""

    lookup = {}

    for record in records:

        player_id = normalize_player_id(
            record.get(
                "id"
            )
        )

        if not player_id:
            continue

        lookup[player_id] = record

    return lookup


def get_pass_usage(record):
    """Read passing usage from player-usage record."""

    usage = record.get(
        "usage",
        {}
    )

    return safe_float(
        usage.get(
            "pass"
        )
    )


def get_overall_usage(record):
    """Read overall usage."""

    usage = record.get(
        "usage",
        {}
    )

    return safe_float(
        usage.get(
            "overall"
        )
    )


def get_average_pass_ppa(record):
    """Read average passing PPA."""

    average = record.get(
        "averagePPA",
        {}
    )

    return safe_float(
        average.get(
            "pass"
        )
    )


def get_total_pass_ppa(record):
    """Read total passing PPA."""

    total = record.get(
        "totalPPA",
        {}
    )

    return safe_float(
        total.get(
            "pass"
        )
    )


def group_usage_by_team(records):
    """Group QB usage records by team."""

    teams = {}

    for record in records:

        team = record.get(
            "team"
        )

        if not team:
            continue

        teams.setdefault(
            team,
            []
        ).append(
            record
        )

    return teams


def rank_team_qbs(records):
    """Rank team QBs by passing usage."""

    return sorted(
        records,
        key=lambda record:
            (
                get_pass_usage(
                    record
                ),
                get_overall_usage(
                    record
                ),
            ),
        reverse=True,
    )


def determine_next_season_status(
    player_id,
    previous_team,
    next_roster_lookup
):
    """
    Determine what happened to a QB in the next season.

    Returns:
        returned_same_team
        transferred
        left_roster
    """

    next_record = next_roster_lookup.get(
        player_id
    )

    if not next_record:

        return {
            "status":
                "left_roster",

            "next_team":
                None,

            "returned_same_team":
                False,

            "transferred":
                False,

            "left_roster":
                True,
        }

    next_team = next_record.get(
        "team"
    )

    if next_team == previous_team:

        return {
            "status":
                "returned_same_team",

            "next_team":
                next_team,

            "returned_same_team":
                True,

            "transferred":
                False,

            "left_roster":
                False,
        }

    return {
        "status":
            "transferred",

        "next_team":
            next_team,

        "returned_same_team":
            False,

        "transferred":
            True,

        "left_roster":
            False,
    }


def build_qb_record(
    usage_record,
    ppa_lookup,
    roster_lookup,
    next_roster_lookup,
    previous_team
):
    """Build one detailed QB record."""

    player_id = normalize_player_id(
        usage_record.get(
            "id"
        )
    )

    ppa_record = ppa_lookup.get(
        player_id,
        {}
    )

    roster_record = roster_lookup.get(
        player_id,
        {}
    )

    next_status = (
        determine_next_season_status(
            player_id,
            previous_team,
            next_roster_lookup
        )
    )

    return {
        "player_id":
            player_id,

        "name":
            usage_record.get(
                "name"
            ),

        "team":
            previous_team,

        "class_year":
            roster_record.get(
                "year"
            ),

        "pass_usage":
            get_pass_usage(
                usage_record
            ),

        "overall_usage":
            get_overall_usage(
                usage_record
            ),

        "average_pass_ppa":
            get_average_pass_ppa(
                ppa_record
            ),

        "total_pass_ppa":
            get_total_pass_ppa(
                ppa_record
            ),

        **next_status,
    }


def build_team_profile(
    team,
    ranked_qbs,
    ppa_lookup,
    roster_lookup,
    next_roster_lookup,
    target_year
):
    """Build continuity profile for one team."""

    primary_usage = (
        ranked_qbs[0]
        if ranked_qbs
        else None
    )

    secondary_usage = (
        ranked_qbs[1]
        if len(ranked_qbs) > 1
        else None
    )

    primary = None
    secondary = None

    if primary_usage:

        primary = build_qb_record(
            primary_usage,
            ppa_lookup,
            roster_lookup,
            next_roster_lookup,
            team
        )

    if secondary_usage:

        secondary = build_qb_record(
            secondary_usage,
            ppa_lookup,
            roster_lookup,
            next_roster_lookup,
            team
        )

    continuity_score = 0.0

    returning_primary_usage = 0.0
    lost_primary_usage = 0.0
    returning_primary_quality = 0.0
    lost_primary_quality = 0.0

    if primary:

        if primary[
            "returned_same_team"
        ]:

            returning_primary_usage = (
                primary[
                    "pass_usage"
                ]
            )

            returning_primary_quality = (
                primary[
                    "average_pass_ppa"
                ]
            )

            continuity_score = (
                primary[
                    "pass_usage"
                ]
            )

        else:

            lost_primary_usage = (
                primary[
                    "pass_usage"
                ]
            )

            lost_primary_quality = (
                primary[
                    "average_pass_ppa"
                ]
            )

            continuity_score = (
                -primary[
                    "pass_usage"
                ]
            )

    primary_secondary_gap = 0.0

    if (
        primary
        and secondary
    ):

        primary_secondary_gap = (
            primary[
                "pass_usage"
            ]
            -
            secondary[
                "pass_usage"
            ]
        )

    return {
        "season":
            target_year,

        "team":
            team,

        "primary_qb":
            primary,

        "secondary_qb":
            secondary,

        "primary_returned":
            bool(
                primary
                and primary[
                    "returned_same_team"
                ]
            ),

        "primary_transferred":
            bool(
                primary
                and primary[
                    "transferred"
                ]
            ),

        "primary_left_roster":
            bool(
                primary
                and primary[
                    "left_roster"
                ]
            ),

        "primary_pass_usage":
            (
                primary[
                    "pass_usage"
                ]
                if primary
                else 0.0
            ),

        "primary_average_pass_ppa":
            (
                primary[
                    "average_pass_ppa"
                ]
                if primary
                else 0.0
            ),

        "primary_total_pass_ppa":
            (
                primary[
                    "total_pass_ppa"
                ]
                if primary
                else 0.0
            ),

        "secondary_pass_usage":
            (
                secondary[
                    "pass_usage"
                ]
                if secondary
                else 0.0
            ),

        "primary_secondary_usage_gap":
            primary_secondary_gap,

        "returning_primary_usage":
            returning_primary_usage,

        "lost_primary_usage":
            lost_primary_usage,

        "returning_primary_quality":
            returning_primary_quality,

        "lost_primary_quality":
            lost_primary_quality,

        "continuity_score":
            continuity_score,
    }


def calculate_qb_continuity(target_year):
    """Calculate QB continuity entering target season."""

    previous_year = (
        target_year
        -
        1
    )

    previous_directory = season_directory(
        previous_year
    )

    target_directory = season_directory(
        target_year
    )

    usage_file = (
        previous_directory
        / "player_usage_qbs.json"
    )

    ppa_file = (
        previous_directory
        / "player_ppa_qbs.json"
    )

    previous_roster_file = (
        previous_directory
        / "roster_qbs.json"
    )

    target_roster_file = (
        target_directory
        / "roster_qbs.json"
    )

    required_files = [
        usage_file,
        ppa_file,
        previous_roster_file,
        target_roster_file,
    ]

    for path in required_files:

        if not path.exists():

            raise FileNotFoundError(
                f"QB continuity input missing: "
                f"{path}"
            )

    usage_records = load_json(
        usage_file
    )

    ppa_records = load_json(
        ppa_file
    )

    previous_roster = load_json(
        previous_roster_file
    )

    target_roster = load_json(
        target_roster_file
    )

    usage_by_team = group_usage_by_team(
        usage_records
    )

    ppa_lookup = build_player_lookup(
        ppa_records
    )

    previous_roster_lookup = (
        build_player_lookup(
            previous_roster
        )
    )

    target_roster_lookup = (
        build_player_lookup(
            target_roster
        )
    )

    profiles = []

    for team in sorted(
        usage_by_team
    ):

        ranked_qbs = rank_team_qbs(
            usage_by_team[
                team
            ]
        )

        profile = build_team_profile(
            team,
            ranked_qbs,
            ppa_lookup,
            previous_roster_lookup,
            target_roster_lookup,
            target_year
        )

        profiles.append(
            profile
        )

    destination = output_file(
        target_year
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with destination.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            profiles,
            file,
            indent=4
        )

    returning_primary = sum(
        1
        for team in profiles
        if team[
            "primary_returned"
        ]
    )

    transferred_primary = sum(
        1
        for team in profiles
        if team[
            "primary_transferred"
        ]
    )

    left_primary = sum(
        1
        for team in profiles
        if team[
            "primary_left_roster"
        ]
    )

    print("=" * 72)

    print(
        f"{target_year} QB CONTINUITY METRICS"
    )

    print("=" * 72)

    print(
        f"Teams processed: "
        f"{len(profiles)}"
    )

    print(
        f"Primary QBs returning to same team: "
        f"{returning_primary}"
    )

    print(
        f"Primary QBs transferring: "
        f"{transferred_primary}"
    )

    print(
        f"Primary QBs leaving college roster: "
        f"{left_primary}"
    )

    print()

    print(
        "TOP 15 RETURNING PRIMARY QBS BY PASS USAGE"
    )

    print("-" * 72)

    returning = [
        team
        for team in profiles
        if team[
            "primary_returned"
        ]
    ]

    returning.sort(
        key=lambda team:
            team[
                "primary_pass_usage"
            ],
        reverse=True,
    )

    for team in returning[:15]:

        qb = team[
            "primary_qb"
        ]

        print(
            f"{team['team']}: "
            f"{qb['name']}, "
            f"usage="
            f"{team['primary_pass_usage']:.3f}, "
            f"avg_pass_PPA="
            f"{team['primary_average_pass_ppa']:+.3f}, "
            f"total_pass_PPA="
            f"{team['primary_total_pass_ppa']:+.1f}"
        )

    print()

    print(
        "TOP 15 LOST PRIMARY QBS BY PASS USAGE"
    )

    print("-" * 72)

    lost = [
        team
        for team in profiles
        if (
            team[
                "primary_transferred"
            ]
            or team[
                "primary_left_roster"
            ]
        )
    ]

    lost.sort(
        key=lambda team:
            team[
                "primary_pass_usage"
            ],
        reverse=True,
    )

    for team in lost[:15]:

        qb = team[
            "primary_qb"
        ]

        print(
            f"{team['team']}: "
            f"{qb['name']}, "
            f"usage="
            f"{team['primary_pass_usage']:.3f}, "
            f"avg_pass_PPA="
            f"{team['primary_average_pass_ppa']:+.3f}, "
            f"status="
            f"{qb['status']}, "
            f"next_team="
            f"{qb['next_team']}"
        )

    print()

    print(
        f"Saved to {destination}"
    )


if __name__ == "__main__":

    target_year = 2025

    if len(sys.argv) > 1:

        target_year = int(
            sys.argv[1]
        )

    calculate_qb_continuity(
        target_year
    )
