"""
Project Gridiron
Coaching Continuity Processor V2

Build preseason-safe coaching continuity metrics.

Usage:
    python -m ratings.coaching_continuity_v2 2025

Historical example:
    2024 coaching situation
        ->
    preseason coaching situation entering 2025

Inputs:
    data/raw/coaching/2024/coaches.json
    data/raw/coaching/2024/coach_seasons.json
    data/raw/coaching/2025/coaches.json
    data/raw/coaching/2025/coach_seasons.json

Output:
    data/processed/coaching_continuity_v2_2025.json

Important:
This version is designed specifically for a PRESEASON model.

It attempts to identify the head coach in place entering the target
season, rather than accidentally selecting an interim or replacement
coach hired later during that season.

This module does NOT modify production ratings.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# PRESEASON CUTOFF
# ============================================================

# We use August 1 as a conservative preseason cutoff.
#
# A coach hired after this date is assumed NOT to have been the
# preseason head coach for modeling purposes.
#
# This protects the historical validation from leaking in-season
# coaching changes into preseason inputs.

PRESEASON_CUTOFF_MONTH = 8
PRESEASON_CUTOFF_DAY = 1


# ============================================================
# PATHS
# ============================================================

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
        / f"coaching_continuity_v2_{year}.json"
    )


# ============================================================
# GENERAL HELPERS
# ============================================================

def load_json(path):
    """Load JSON."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(
            file
        )


def safe_float(value):
    """Safely convert value to float."""

    if value is None:
        return 0.0

    try:

        return float(
            value
        )

    except (
        TypeError,
        ValueError
    ):

        return 0.0


def safe_int(value):
    """Safely convert value to int."""

    if value is None:
        return 0

    try:

        return int(
            value
        )

    except (
        TypeError,
        ValueError
    ):

        return 0


def normalize_coach_id(value):
    """Normalize coach ID."""

    if value is None:
        return None

    return str(
        value
    ).strip()


def parse_date(value):
    """Parse ISO date."""

    if not value:
        return None

    try:

        return datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00"
            )
        )

    except (
        ValueError,
        TypeError,
        AttributeError
    ):

        return None


def preseason_cutoff(year):
    """Return target-season preseason cutoff."""

    return datetime(
        year,
        PRESEASON_CUTOFF_MONTH,
        PRESEASON_CUTOFF_DAY,
        tzinfo=timezone.utc,
    )


# ============================================================
# COACH METADATA
# ============================================================

def coach_name(record):
    """Return coach name from /coaches record."""

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

    name = (
        f"{first_name} {last_name}"
    ).strip()

    return name or None


def season_coach_name(record):
    """Return coach name from coach-season record."""

    if not record:
        return None

    coach = (
        record.get(
            "coach"
        )
        or {}
    )

    if not isinstance(
        coach,
        dict
    ):
        return None

    first_name = (
        coach.get(
            "firstName"
        )
        or ""
    )

    last_name = (
        coach.get(
            "lastName"
        )
        or ""
    )

    name = (
        f"{first_name} {last_name}"
    ).strip()

    return name or None


def build_coach_metadata_lookup(records):
    """Build coach metadata lookup."""

    lookup = {}

    for record in records:

        if not isinstance(
            record,
            dict
        ):
            continue

        coach_id = normalize_coach_id(
            record.get(
                "id"
            )
        )

        if not coach_id:
            continue

        lookup[
            coach_id
        ] = {
            "coach_id":
                coach_id,

            "name":
                coach_name(
                    record
                ),

            "hire_date":
                record.get(
                    "hireDate"
                ),

            "hire_datetime":
                parse_date(
                    record.get(
                        "hireDate"
                    )
                ),

            "seasons":
                (
                    record.get(
                        "seasons"
                    )
                    or []
                ),
        }

    return lookup


# ============================================================
# TEAM / SEASON HELPERS
# ============================================================

def group_season_records_by_team(records):
    """Group coach-season records by school."""

    teams = {}

    for record in records:

        if not isinstance(
            record,
            dict
        ):
            continue

        team = (
            record.get(
                "team"
            )
            or {}
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


def coach_id_from_season(record):
    """Return coach ID from coach-season record."""

    if not record:
        return None

    coach = (
        record.get(
            "coach"
        )
        or {}
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


# ============================================================
# PRIMARY / PRESEASON COACH SELECTION
# ============================================================

def choose_prior_primary_coach(records):
    """
    Choose prior-season primary coach.

    For the completed prior season, using games coached is fine.
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
            ),
        reverse=True,
    )

    return ranked[0]


def coach_was_hired_before_preseason(
    coach_id,
    metadata_lookup,
    target_year
):
    """
    Return whether coach was hired before target preseason cutoff.
    """

    metadata = metadata_lookup.get(
        coach_id,
        {}
    )

    hire_datetime = metadata.get(
        "hire_datetime"
    )

    if hire_datetime is None:
        return True

    return (
        hire_datetime
        <=
        preseason_cutoff(
            target_year
        )
    )


def choose_preseason_current_coach(
    records,
    metadata_lookup,
    target_year
):
    """
    Identify coach in place entering target season.

    Rules:

    1. Keep coaches hired on/before August 1.
    2. Exclude later in-season hires.
    3. If multiple candidates remain, prefer the one with the
       earliest hire date.
    4. Fall back to most games only if hire-date metadata is missing.
    """

    if not records:
        return None

    eligible = []

    for record in records:

        coach_id = coach_id_from_season(
            record
        )

        if not coach_id:
            continue

        if coach_was_hired_before_preseason(
            coach_id,
            metadata_lookup,
            target_year
        ):

            eligible.append(
                record
            )

    if not eligible:

        # Conservative fallback.
        #
        # If metadata is incomplete, use the record with the most games,
        # but this should be rare and will be visible in diagnostics.

        return choose_prior_primary_coach(
            records
        )

    def sort_key(record):

        coach_id = coach_id_from_season(
            record
        )

        metadata = metadata_lookup.get(
            coach_id,
            {}
        )

        hire_datetime = metadata.get(
            "hire_datetime"
        )

        if hire_datetime is None:

            hire_timestamp = float(
                "inf"
            )

        else:

            hire_timestamp = (
                hire_datetime.timestamp()
            )

        return (
            hire_timestamp,
            -
            safe_int(
                record.get(
                    "games"
                )
            ),
        )

    eligible.sort(
        key=sort_key
    )

    return eligible[0]


# ============================================================
# TENURE
# ============================================================

def calculate_tenure_years(
    metadata,
    target_year
):
    """
    Estimate years at current program from hire date.
    """

    if not metadata:
        return 0

    hire_datetime = metadata.get(
        "hire_datetime"
    )

    if not hire_datetime:
        return 0

    hire_year = hire_datetime.year

    tenure = (
        target_year
        -
        hire_year
        +
        1
    )

    return max(
        tenure,
        1
    )


# ============================================================
# PRIOR PERFORMANCE
# ============================================================

def extract_prior_performance(record):
    """Extract completed prior-season context."""

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

    scoring = (
        record.get(
            "scoring"
        )
        or {}
    )

    if not isinstance(
        scoring,
        dict
    ):
        scoring = {}

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


# ============================================================
# TEAM PROFILE
# ============================================================

def build_team_profile(
    team,
    prior_record,
    current_record,
    prior_metadata_lookup,
    current_metadata_lookup,
    target_year
):
    """Build preseason-safe coaching profile."""

    prior_coach_id = coach_id_from_season(
        prior_record
    )

    current_coach_id = coach_id_from_season(
        current_record
    )

    prior_metadata = (
        prior_metadata_lookup.get(
            prior_coach_id,
            {}
        )
        if prior_coach_id
        else {}
    )

    current_metadata = (
        current_metadata_lookup.get(
            current_coach_id,
            {}
        )
        if current_coach_id
        else {}
    )

    same_head_coach = (
        prior_coach_id is not None
        and
        current_coach_id is not None
        and
        prior_coach_id
        ==
        current_coach_id
    )

    new_head_coach = (
        prior_coach_id is not None
        and
        current_coach_id is not None
        and
        prior_coach_id
        !=
        current_coach_id
    )

    tenure_years = calculate_tenure_years(
        current_metadata,
        target_year
    )

    first_year_current_program = (
        tenure_years == 1
    )

    second_year_current_program = (
        tenure_years == 2
    )

    established_coach = (
        tenure_years >= 3
    )

    long_tenure = (
        tenure_years >= 5
    )

    prior_performance = extract_prior_performance(
        prior_record
    )

    # ------------------------------------------------------------
    # INTERACTION VARIABLES
    # ------------------------------------------------------------

    change_after_bad_sp = (
        1.0
        if (
            new_head_coach
            and
            prior_performance[
                "sp_overall"
            ] < -10.0
        )
        else 0.0
    )

    change_after_good_sp = (
        1.0
        if (
            new_head_coach
            and
            prior_performance[
                "sp_overall"
            ] > 10.0
        )
        else 0.0
    )

    change_after_losing_season = (
        1.0
        if (
            new_head_coach
            and
            prior_performance[
                "win_percentage"
            ] < 0.500
        )
        else 0.0
    )

    change_after_winning_season = (
        1.0
        if (
            new_head_coach
            and
            prior_performance[
                "win_percentage"
            ] >= 0.500
        )
        else 0.0
    )

    change_x_prior_sp = (
        prior_performance[
            "sp_overall"
        ]
        if new_head_coach
        else 0.0
    )

    change_x_prior_win_pct = (
        prior_performance[
            "win_percentage"
        ]
        if new_head_coach
        else 0.0
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
                season_coach_name(
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
                season_coach_name(
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

        "established_coach":
            established_coach,

        "long_tenure":
            long_tenure,

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

        "change_after_bad_sp":
            change_after_bad_sp,

        "change_after_good_sp":
            change_after_good_sp,

        "change_after_losing_season":
            change_after_losing_season,

        "change_after_winning_season":
            change_after_winning_season,

        "change_x_prior_sp":
            change_x_prior_sp,

        "change_x_prior_win_pct":
            change_x_prior_win_pct,
    }


# ============================================================
# MAIN
# ============================================================

def calculate_coaching_continuity_v2(
    target_year
):
    """Calculate preseason-safe coaching continuity."""

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
                f"Coaching continuity V2 input missing: "
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
        &
        set(
            current_by_team
        )
    )

    profiles = []

    for team in teams:

        prior_record = choose_prior_primary_coach(
            prior_by_team[
                team
            ]
        )

        current_record = (
            choose_preseason_current_coach(
                current_by_team[
                    team
                ],
                current_metadata_lookup,
                target_year
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

    same_count = sum(
        1
        for profile in profiles
        if profile[
            "same_head_coach"
        ]
    )

    new_count = sum(
        1
        for profile in profiles
        if profile[
            "new_head_coach"
        ]
    )

    first_year_count = sum(
        1
        for profile in profiles
        if profile[
            "first_year_current_program"
        ]
    )

    second_year_count = sum(
        1
        for profile in profiles
        if profile[
            "second_year_current_program"
        ]
    )

    change_after_bad = sum(
        1
        for profile in profiles
        if profile[
            "change_after_bad_sp"
        ]
    )

    change_after_good = sum(
        1
        for profile in profiles
        if profile[
            "change_after_good_sp"
        ]
    )

    print("=" * 78)

    print(
        f"{target_year} COACHING CONTINUITY V2"
    )

    print("=" * 78)

    print(
        f"Teams processed: "
        f"{len(profiles)}"
    )

    print(
        f"Same preseason head coach: "
        f"{same_count}"
    )

    print(
        f"New preseason head coach: "
        f"{new_count}"
    )

    print(
        f"First-year current-program coaches: "
        f"{first_year_count}"
    )

    print(
        f"Second-year current-program coaches: "
        f"{second_year_count}"
    )

    print(
        f"Coaching changes after SP+ < -10: "
        f"{change_after_bad}"
    )

    print(
        f"Coaching changes after SP+ > +10: "
        f"{change_after_good}"
    )

    print()

    print(
        "PRESEASON HEAD-COACH CHANGES"
    )

    print("-" * 78)

    changed = [
        profile
        for profile in profiles
        if profile[
            "new_head_coach"
        ]
    ]

    changed.sort(
        key=lambda profile:
            profile[
                "prior_coach_sp_overall"
            ]
    )

    for profile in changed:

        print(
            f"{profile['team']}: "
            f"{profile['prior_head_coach']['name']} -> "
            f"{profile['current_head_coach']['name']}, "
            f"prior_SP="
            f"{profile['prior_coach_sp_overall']:+.1f}, "
            f"prior_win%="
            f"{profile['prior_coach_win_percentage']:.3f}, "
            f"hire_date="
            f"{profile['current_head_coach']['hire_date']}"
        )

    print()

    print(
        "LONGEST PRESEASON COACH TENURES"
    )

    print("-" * 78)

    longest = sorted(
        profiles,
        key=lambda profile:
            profile[
                "tenure_years"
            ],
        reverse=True,
    )

    for profile in longest[:15]:

        print(
            f"{profile['team']}: "
            f"{profile['current_head_coach']['name']}, "
            f"tenure="
            f"{profile['tenure_years']} years"
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

    calculate_coaching_continuity_v2(
        target_year
    )
