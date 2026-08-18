"""
Project Gridiron
Coaching Continuity Processor

Build team-level coaching continuity metrics for a target season.

Historical example:
    2024 coaching data -> 2025 coaching situation

Usage:
    python -m ratings.coaching_continuity 2025

Inputs:
    data/raw/coaching/2024/coaches.json
    data/raw/coaching/2024/coach_seasons.json
    data/raw/coaching/2025/coaches.json
    data/raw/coaching/2025/coach_seasons.json

Output:
    data/processed/coaching_continuity_2025.json

Important:
Some teams can have multiple coach-season records in a year because
of interim coaching changes. The primary coach for a team-season is
defined as the coach credited with the most games.

This module does NOT modify production ratings.
"""

import json
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def coaching_directory(year):
    """Return raw coaching directory."""

    return (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "coaching"
        / str(year)
    )


def output_file(year):
    """Return processed output path."""

    return (
        PROJECT_ROOT
        / "data"
        / "processed"
        / f"coaching_continuity_{year}.json"
    )


def load_json(path):
    """Load JSON."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def safe_float(value):
    """Safely convert to float."""

    if value is None:
        return 0.0

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return 0.0


def safe_int(value):
    """Safely convert to int."""

    if value is None:
        return 0

    try:
        return int(value)

    except (
        TypeError,
        ValueError
    ):
        return 0


def normalize_coach_id(value):
    """Normalize coach ID."""

    if value is None:
        return None

    return str(value).strip()


def full_coach_name(record):
    """Return coach full name."""

    first_name = (
        record.get(
            "firstName"
        )
        or ""
    )

    last_name = (
        record.get(
            "lastName"
        )
        or ""
    )

    return (
        f"{first_name} {last_name}"
    ).strip()


def parse_date(value):
    """Parse ISO date safely."""

    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        )

    except ValueError:
        return None


def build_coach_metadata_lookup(records):
    """Build lookup from /coaches records."""

    lookup = {}

    for record in records:

        coach_id = normalize_coach_id(
            record.get(
                "id"
            )
        )

        if not coach_id:
            continue

        seasons = (
            record.get(
                "seasons"
            )
            or []
        )

        lookup[
            coach_id
        ] = {
            "coach_id":
                coach_id,

            "name":
                full_coach_name(
                    record
                ),

            "hire_date":
                record.get(
                    "hireDate"
                ),

            "seasons":
                seasons,

            "career_season_count":
                len(
                    seasons
                ),
        }

    return lookup


def group_season_records_by_team(records):
    """Group coach-season records by team."""

    teams = {}

    for record in records:

        team = record.get(
            "team",
            {}
        )

        if not isinstance(
            team,
            dict
        ):
            continue

        school = team.get(
            "school"
        )

        if not school:
            continue

        teams.setdefault(
            school,
            []
        ).append(
            record
        )

    return teams


def choose_primary_coach(records):
    """
    Choose primary coach for one team-season.

    Highest games coached wins.
    Ties are broken by wins, then coach ID.
    """

    if not records:
        return None

    ranked = sorted(
        records,
        key=lambda record:
            (
                safe_int(
                    record.get(
                        "games"
                    )
                ),
                safe_int(
                    record.get(
                        "wins"
                    )
                ),
                normalize_coach_id(
                    record.get(
                        "coach",
                        {}
                    ).get(
                        "id"
                    )
                ) or "",
            ),
        reverse=True,
    )

    return ranked[0]


def coach_id_from_season(record):
    """Read coach ID from coach-season record."""

    if not record:
        return None

    coach = record.get(
        "coach",
        {}
    )

    if not isinstance(
        coach,
        dict
    ):
        return None

    return normalize_coach_id(
        coach.get(
            "id"
        )
    )


def coach_name_from_season(record):
    """Read coach name from coach-season record."""

    if not record:
        return None

    coach = record.get(
        "coach",
        {}
    )

    if not isinstance(
        coach,
        dict
    ):
        return None

    return (
        f"{coach.get('firstName', '')} "
        f"{coach.get('lastName', '')}"
    ).strip()


def calculate_tenure_years(
    metadata,
    season_year
):
    """
    Estimate years in current job using hire date.

    This is intentionally conservative.
    """

    if not metadata:
        return 0

    hire_date = parse_date(
        metadata.get(
            "hire_date"
        )
    )

    if not hire_date:
        return 0

    hire_year = hire_date.year

    tenure = (
        season_year
        -
        hire_year
        +
        1
    )

    return max(
        tenure,
        1
    )


def prior_head_coach_history(
    metadata,
    current_team,
    current_year
):
    """
    Count prior head-coaching seasons before current season.

    This uses season history returned by /coaches.
    """

    if not metadata:
        return {
            "prior_head_coaching_seasons":
                0,

            "prior_other_team_seasons":
                0,

            "prior_total_wins":
                0,

            "prior_total_losses":
                0,
        }

    prior_head_coaching_seasons = 0
    prior_other_team_seasons = 0
    prior_total_wins = 0
    prior_total_losses = 0

    for season in metadata.get(
        "seasons",
        []
    ):

        year = safe_int(
            season.get(
                "year"
            )
        )

        if year >= current_year:
            continue

        prior_head_coaching_seasons += 1

        if season.get(
            "school"
        ) != current_team:

            prior_other_team_seasons += 1

        prior_total_wins += safe_int(
            season.get(
                "wins"
            )
        )

        prior_total_losses += safe_int(
            season.get(
                "losses"
            )
        )

    return {
        "prior_head_coaching_seasons":
            prior_head_coaching_seasons,

        "prior_other_team_seasons":
            prior_other_team_seasons,

        "prior_total_wins":
            prior_total_wins,

        "prior_total_losses":
            prior_total_losses,
    }


def extract_prior_performance(record):
    """Extract prior-season coaching performance."""

    if not record:
        return {
            "games":
                0,

            "wins":
                0,

            "losses":
                0,

            "win_percentage":
                0.0,

            "srs":
                0.0,

            "sp_overall":
                0.0,

            "sp_offense":
                0.0,

            "sp_defense":
                0.0,

            "point_differential":
                0.0,
        }

    scoring = record.get(
        "scoring",
        {}
    )

    return {
        "games":
            safe_int(
                record.get(
                    "games"
                )
            ),

        "wins":
            safe_int(
                record.get(
                    "wins"
                )
            ),

        "losses":
            safe_int(
                record.get(
                    "losses"
                )
            ),

        "win_percentage":
            safe_float(
                record.get(
                    "winPercentage"
                )
            ),

        "srs":
            safe_float(
                record.get(
                    "srs"
                )
            ),

        "sp_overall":
            safe_float(
                record.get(
                    "spOverall"
                )
            ),

        "sp_offense":
            safe_float(
                record.get(
                    "spOffense"
                )
            ),

        "sp_defense":
            safe_float(
                record.get(
                    "spDefense"
                )
            ),

        "point_differential":
            safe_float(
                scoring.get(
                    "averagePointDifferential"
                )
            ),
    }


def build_team_profile(
    team,
    prior_record,
    current_record,
    prior_metadata_lookup,
    current_metadata_lookup,
    target_year
):
    """Build one coaching continuity profile."""

    prior_coach_id = coach_id_from_season(
        prior_record
    )

    current_coach_id = coach_id_from_season(
        current_record
    )

    same_head_coach = (
        prior_coach_id is not None
        and
        current_coach_id is not None
        and
        prior_coach_id == current_coach_id
    )

    new_head_coach = (
        prior_coach_id is not None
        and
        current_coach_id is not None
        and
        prior_coach_id != current_coach_id
    )

    current_metadata = (
        current_metadata_lookup.get(
            current_coach_id,
            {}
        )
        if current_coach_id
        else {}
    )

    prior_metadata = (
        prior_metadata_lookup.get(
            prior_coach_id,
            {}
        )
        if prior_coach_id
        else {}
    )

    tenure_years = calculate_tenure_years(
        current_metadata,
        target_year
    )

    history = prior_head_coach_history(
        current_metadata,
        team,
        target_year
    )

    first_year_current_program = (
        tenure_years == 1
    )

    second_year_current_program = (
        tenure_years == 2
    )

    experienced_head_coach = (
        history[
            "prior_head_coaching_seasons"
        ]
        > 0
    )

    first_time_head_coach = (
        first_year_current_program
        and
        history[
            "prior_head_coaching_seasons"
        ]
        == 0
    )

    prior_performance = (
        extract_prior_performance(
            prior_record
        )
    )

    return {
        "season":
            target_year,

        "team":
            team,

        "prior_head_coach": {
            "coach_id":
                prior_coach_id,

            "name":
                coach_name_from_season(
                    prior_record
                ),

            "hire_date":
                prior_metadata.get(
                    "hire_date"
                ),
        },

        "current_head_coach": {
            "coach_id":
                current_coach_id,

            "name":
                coach_name_from_season(
                    current_record
                ),

            "hire_date":
                current_metadata.get(
                    "hire_date"
                ),
        },

        "same_head_coach":
            same_head_coach,

        "new_head_coach":
            new_head_coach,

        "tenure_years":
            tenure_years,

        "first_year_current_program":
            first_year_current_program,

        "second_year_current_program":
            second_year_current_program,

        "experienced_head_coach":
            experienced_head_coach,

        "first_time_head_coach":
            first_time_head_coach,

        "prior_head_coaching_seasons":
            history[
                "prior_head_coaching_seasons"
            ],

        "prior_other_team_seasons":
            history[
                "prior_other_team_seasons"
            ],

        "prior_total_wins":
            history[
                "prior_total_wins"
            ],

        "prior_total_losses":
            history[
                "prior_total_losses"
            ],

        "prior_coach_games":
            prior_performance[
                "games"
            ],

        "prior_coach_wins":
            prior_performance[
                "wins"
            ],

        "prior_coach_losses":
            prior_performance[
                "losses"
            ],

        "prior_coach_win_percentage":
            prior_performance[
                "win_percentage"
            ],

        "prior_coach_srs":
            prior_performance[
                "srs"
            ],

        "prior_coach_sp_overall":
            prior_performance[
                "sp_overall"
            ],

        "prior_coach_sp_offense":
            prior_performance[
                "sp_offense"
            ],

        "prior_coach_sp_defense":
            prior_performance[
                "sp_defense"
            ],

        "prior_coach_point_differential":
            prior_performance[
                "point_differential"
            ],
    }


def calculate_coaching_continuity(
    target_year
):
    """Calculate coaching continuity entering target season."""

    prior_year = (
        target_year
        -
        1
    )

    prior_directory = coaching_directory(
        prior_year
    )

    current_directory = coaching_directory(
        target_year
    )

    prior_coaches_file = (
        prior_directory
        / "coaches.json"
    )

    prior_seasons_file = (
        prior_directory
        / "coach_seasons.json"
    )

    current_coaches_file = (
        current_directory
        / "coaches.json"
    )

    current_seasons_file = (
        current_directory
        / "coach_seasons.json"
    )

    required_files = [
        prior_coaches_file,
        prior_seasons_file,
        current_coaches_file,
        current_seasons_file,
    ]

    for path in required_files:

        if not path.exists():

            raise FileNotFoundError(
                f"Coaching continuity input missing: "
                f"{path}"
            )

    prior_coaches = load_json(
        prior_coaches_file
    )

    prior_seasons = load_json(
        prior_seasons_file
    )

    current_coaches = load_json(
        current_coaches_file
    )

    current_seasons = load_json(
        current_seasons_file
    )

    prior_metadata_lookup = (
        build_coach_metadata_lookup(
            prior_coaches
        )
    )

    current_metadata_lookup = (
        build_coach_metadata_lookup(
            current_coaches
        )
    )

    prior_by_team = (
        group_season_records_by_team(
            prior_seasons
        )
    )

    current_by_team = (
        group_season_records_by_team(
            current_seasons
        )
    )

    teams = sorted(
        set(
            prior_by_team
        )
        |
        set(
            current_by_team
        )
    )

    profiles = []

    for team in teams:

        prior_record = choose_primary_coach(
            prior_by_team.get(
                team,
                []
            )
        )

        current_record = choose_primary_coach(
            current_by_team.get(
                team,
                []
            )
        )

        if not prior_record:
            continue

        if not current_record:
            continue

        profile = build_team_profile(
            team,
            prior_record,
            current_record,
            prior_metadata_lookup,
            current_metadata_lookup,
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

    returning_coaches = sum(
        1
        for team in profiles
        if team[
            "same_head_coach"
        ]
    )

    new_coaches = sum(
        1
        for team in profiles
        if team[
            "new_head_coach"
        ]
    )

    first_year = sum(
        1
        for team in profiles
        if team[
            "first_year_current_program"
        ]
    )

    first_time = sum(
        1
        for team in profiles
        if team[
            "first_time_head_coach"
        ]
    )

    experienced_new = sum(
        1
        for team in profiles
        if (
            team[
                "new_head_coach"
            ]
            and
            team[
                "experienced_head_coach"
            ]
        )
    )

    print("=" * 76)

    print(
        f"{target_year} COACHING CONTINUITY"
    )

    print("=" * 76)

    print(
        f"Teams processed: "
        f"{len(profiles)}"
    )

    print(
        f"Same head coach: "
        f"{returning_coaches}"
    )

    print(
        f"New head coach: "
        f"{new_coaches}"
    )

    print(
        f"First-year coaches: "
        f"{first_year}"
    )

    print(
        f"First-time head coaches: "
        f"{first_time}"
    )

    print(
        f"New coaches with prior HC experience: "
        f"{experienced_new}"
    )

    print()

    print(
        "NEW HEAD COACHES"
    )

    print("-" * 76)

    changed = [
        team
        for team in profiles
        if team[
            "new_head_coach"
        ]
    ]

    changed.sort(
        key=lambda team:
            team[
                "prior_coach_sp_overall"
            ]
    )

    for team in changed:

        print(
            f"{team['team']}: "
            f"{team['prior_head_coach']['name']} -> "
            f"{team['current_head_coach']['name']}, "
            f"prior_SP="
            f"{team['prior_coach_sp_overall']:+.1f}, "
            f"prior_win%="
            f"{team['prior_coach_win_percentage']:.3f}, "
            f"new_HC_experience="
            f"{team['prior_head_coaching_seasons']}"
        )

    print()

    print(
        "LONGEST CURRENT TENURES"
    )

    print("-" * 76)

    longest = sorted(
        profiles,
        key=lambda team:
            team[
                "tenure_years"
            ],
        reverse=True,
    )

    for team in longest[:15]:

        print(
            f"{team['team']}: "
            f"{team['current_head_coach']['name']}, "
            f"tenure={team['tenure_years']} years, "
            f"prior_HC_seasons="
            f"{team['prior_head_coaching_seasons']}"
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

    calculate_coaching_continuity(
        target_year
    )
