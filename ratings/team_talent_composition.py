"""
Project Gridiron
Team Talent Composition

Build roster-level talent composition metrics by joining:

    CFBD season roster
        +
    historical CFBD recruiting player records

Usage:
    python -m ratings.team_talent_composition 2024
    python -m ratings.team_talent_composition 2025

Inputs:

    data/raw/qb_data/<year>/roster.json

    data/raw/recruiting_players/2019.json
    ...
    data/raw/recruiting_players/<year>.json

NOTE:
The qb_data directory contains full roster data despite its historical
directory name.

Output:

    data/processed/team_talent_composition_<year>.json

This is different from recruiting-class talent.

Recruiting talent answers:
    "How good was this year's incoming class?"

Team talent composition answers:
    "How talented is the actual roster currently on campus?"

Metrics include:

    roster size
    players matched to recruiting history
    recruiting-rating coverage
    average roster composite
    median roster composite
    top-10 average composite
    top-20 average composite
    blue-chip count / percentage
    elite-player count / percentage
    five-star count
    four-star count
    three-star count
    position-group talent

This module does NOT modify production power ratings.
"""

import json
import statistics
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


RECRUITING_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "recruiting_players"
)


BLUE_CHIP_RATING = 0.8900
ELITE_RATING = 0.9500


# ============================================================
# POSITION GROUPS
# ============================================================

QB_POSITIONS = {
    "QB",
}

SKILL_POSITIONS = {
    "RB",
    "HB",
    "FB",
    "WR",
    "TE",
}

OL_POSITIONS = {
    "OL",
    "OT",
    "T",
    "LT",
    "RT",
    "OG",
    "G",
    "LG",
    "RG",
    "C",
}

DL_POSITIONS = {
    "DL",
    "DT",
    "NT",
    "DE",
    "EDGE",
}

LB_POSITIONS = {
    "LB",
    "ILB",
    "OLB",
    "MLB",
}

DB_POSITIONS = {
    "DB",
    "CB",
    "S",
    "FS",
    "SS",
}


# ============================================================
# PATHS
# ============================================================

def roster_file(year):
    """Return full CFBD roster path."""

    return (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "qb_data"
        / str(year)
        / "roster.json"
    )


def output_file(year):
    """Return processed output path."""

    return (
        PROJECT_ROOT
        / "data"
        / "processed"
        / f"team_talent_composition_{year}.json"
    )


# ============================================================
# GENERAL HELPERS
# ============================================================

def load_json(path):
    """Load JSON file."""

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
        return None

    try:

        return float(
            value
        )

    except (
        TypeError,
        ValueError
    ):

        return None


def normalize_position(value):
    """Normalize position abbreviation."""

    if not value:
        return "UNKNOWN"

    return (
        str(value)
        .strip()
        .upper()
    )


def classify_position(position):
    """Map detailed positions into broad groups."""

    position = normalize_position(
        position
    )

    if position in QB_POSITIONS:
        return "QB"

    if position in SKILL_POSITIONS:
        return "SKILL"

    if position in OL_POSITIONS:
        return "OL"

    if position in DL_POSITIONS:
        return "DL"

    if position in LB_POSITIONS:
        return "LB"

    if position in DB_POSITIONS:
        return "DB"

    return "OTHER"


def average(values):
    """Safely calculate average."""

    if not values:
        return 0.0

    return (
        sum(values)
        /
        len(values)
    )


# ============================================================
# RECRUITING HISTORY
# ============================================================

def load_recruiting_history(year):
    """
    Load recruiting records capable of matching players
    on the target-season roster.
    """

    records = []

    loaded_years = []

    for recruiting_year in range(
        2019,
        year + 1
    ):

        path = (
            RECRUITING_DIRECTORY
            / f"{recruiting_year}.json"
        )

        if not path.exists():
            continue

        year_records = load_json(
            path
        )

        records.extend(
            year_records
        )

        loaded_years.append(
            recruiting_year
        )

    return (
        records,
        loaded_years,
    )


def build_recruiting_index(records):
    """
    Index recruiting records by CFBD recruiting ID.

    Roster records expose recruitIds such as:

        "recruitIds": ["112029"]

    Recruiting records expose:

        "id": "112029"
    """

    index = {}

    for record in records:

        recruit_id = record.get(
            "id"
        )

        if recruit_id is None:
            continue

        recruit_id = str(
            recruit_id
        ).strip()

        if not recruit_id:
            continue

        index[
            recruit_id
        ] = record

    return index


# ============================================================
# PLAYER MATCHING
# ============================================================

def find_recruiting_record(
    roster_player,
    recruiting_index
):
    """Match roster player using recruitIds."""

    recruit_ids = roster_player.get(
        "recruitIds"
    ) or []

    for recruit_id in recruit_ids:

        recruit_id = str(
            recruit_id
        ).strip()

        recruiting_record = (
            recruiting_index.get(
                recruit_id
            )
        )

        if recruiting_record:

            return recruiting_record

    return None


# ============================================================
# POSITION PROFILE
# ============================================================

def empty_position_profile():
    """Create empty position-group profile."""

    return {
        "roster_count": 0,

        "rated_count": 0,

        "rating_sum": 0.0,

        "average_rating": 0.0,

        "blue_chip_count": 0,

        "elite_count": 0,

        "five_star_count": 0,

        "four_star_count": 0,
    }


def add_position_player(
    profile,
    rating,
    stars
):
    """Add player to position profile."""

    profile[
        "roster_count"
    ] += 1

    if rating is None:
        return

    profile[
        "rated_count"
    ] += 1

    profile[
        "rating_sum"
    ] += rating

    if rating >= BLUE_CHIP_RATING:

        profile[
            "blue_chip_count"
        ] += 1

    if rating >= ELITE_RATING:

        profile[
            "elite_count"
        ] += 1

    if stars == 5:

        profile[
            "five_star_count"
        ] += 1

    elif stars == 4:

        profile[
            "four_star_count"
        ] += 1


def finalize_position_profile(
    profile
):
    """Calculate position-group averages."""

    if profile[
        "rated_count"
    ]:

        profile[
            "average_rating"
        ] = (
            profile[
                "rating_sum"
            ]
            /
            profile[
                "rated_count"
            ]
        )

    profile[
        "rating_sum"
    ] = round(
        profile[
            "rating_sum"
        ],
        4
    )

    profile[
        "average_rating"
    ] = round(
        profile[
            "average_rating"
        ],
        4
    )

    return profile


# ============================================================
# TEAM PROFILE
# ============================================================

def create_team_profile(
    team,
    year
):
    """Create empty team talent profile."""

    return {
        "season":
            year,

        "team":
            team,

        "roster_size":
            0,

        "players_with_recruit_id":
            0,

        "matched_recruiting_players":
            0,

        "rated_players":
            0,

        "rating_coverage":
            0.0,

        "average_rating":
            0.0,

        "median_rating":
            0.0,

        "top_10_average_rating":
            0.0,

        "top_20_average_rating":
            0.0,

        "top_30_average_rating":
            0.0,

        "blue_chip_count":
            0,

        "blue_chip_percentage":
            0.0,

        "elite_count":
            0,

        "elite_percentage":
            0.0,

        "five_star_count":
            0,

        "four_star_count":
            0,

        "three_star_count":
            0,

        "two_star_count":
            0,

        "position_groups": {
            "QB":
                empty_position_profile(),

            "SKILL":
                empty_position_profile(),

            "OL":
                empty_position_profile(),

            "DL":
                empty_position_profile(),

            "LB":
                empty_position_profile(),

            "DB":
                empty_position_profile(),

            "OTHER":
                empty_position_profile(),
        },

        "_ratings": [],
    }


def add_roster_player(
    profile,
    roster_player,
    recruiting_record
):
    """Add one current roster player."""

    profile[
        "roster_size"
    ] += 1

    recruit_ids = roster_player.get(
        "recruitIds"
    ) or []

    if recruit_ids:

        profile[
            "players_with_recruit_id"
        ] += 1

    position_group = classify_position(
        roster_player.get(
            "position"
        )
    )

    position_profile = (
        profile[
            "position_groups"
        ][
            position_group
        ]
    )

    # Count roster presence even if no recruiting match exists.
    if not recruiting_record:

        position_profile[
            "roster_count"
        ] += 1

        return

    profile[
        "matched_recruiting_players"
    ] += 1

    rating = safe_float(
        recruiting_record.get(
            "rating"
        )
    )

    stars = recruiting_record.get(
        "stars"
    )

    # Position group player.
    add_position_player(
        position_profile,
        rating,
        stars
    )

    if rating is None:
        return

    profile[
        "rated_players"
    ] += 1

    profile[
        "_ratings"
    ].append(
        rating
    )

    if rating >= BLUE_CHIP_RATING:

        profile[
            "blue_chip_count"
        ] += 1

    if rating >= ELITE_RATING:

        profile[
            "elite_count"
        ] += 1

    if stars == 5:

        profile[
            "five_star_count"
        ] += 1

    elif stars == 4:

        profile[
            "four_star_count"
        ] += 1

    elif stars == 3:

        profile[
            "three_star_count"
        ] += 1

    elif stars == 2:

        profile[
            "two_star_count"
        ] += 1


def finalize_team_profile(
    profile
):
    """Calculate final roster talent metrics."""

    ratings = sorted(
        profile[
            "_ratings"
        ],
        reverse=True,
    )

    rated_count = len(
        ratings
    )

    if profile[
        "roster_size"
    ]:

        profile[
            "rating_coverage"
        ] = (
            rated_count
            /
            profile[
                "roster_size"
            ]
        )

    if ratings:

        profile[
            "average_rating"
        ] = average(
            ratings
        )

        profile[
            "median_rating"
        ] = statistics.median(
            ratings
        )

        profile[
            "top_10_average_rating"
        ] = average(
            ratings[:10]
        )

        profile[
            "top_20_average_rating"
        ] = average(
            ratings[:20]
        )

        profile[
            "top_30_average_rating"
        ] = average(
            ratings[:30]
        )

        profile[
            "blue_chip_percentage"
        ] = (
            profile[
                "blue_chip_count"
            ]
            /
            rated_count
        )

        profile[
            "elite_percentage"
        ] = (
            profile[
                "elite_count"
            ]
            /
            rated_count
        )

    profile[
        "rating_coverage"
    ] = round(
        profile[
            "rating_coverage"
        ],
        4
    )

    profile[
        "average_rating"
    ] = round(
        profile[
            "average_rating"
        ],
        4
    )

    profile[
        "median_rating"
    ] = round(
        profile[
            "median_rating"
        ],
        4
    )

    profile[
        "top_10_average_rating"
    ] = round(
        profile[
            "top_10_average_rating"
        ],
        4
    )

    profile[
        "top_20_average_rating"
    ] = round(
        profile[
            "top_20_average_rating"
        ],
        4
    )

    profile[
        "top_30_average_rating"
    ] = round(
        profile[
            "top_30_average_rating"
        ],
        4
    )

    profile[
        "blue_chip_percentage"
    ] = round(
        profile[
            "blue_chip_percentage"
        ],
        4
    )

    profile[
        "elite_percentage"
    ] = round(
        profile[
            "elite_percentage"
        ],
        4
    )

    for group in profile[
        "position_groups"
    ]:

        profile[
            "position_groups"
        ][
            group
        ] = (
            finalize_position_profile(
                profile[
                    "position_groups"
                ][
                    group
                ]
            )
        )

    del profile[
        "_ratings"
    ]

    return profile


# ============================================================
# MAIN
# ============================================================

def calculate_team_talent_composition(
    year
):
    """Build roster talent composition for one season."""

    source = roster_file(
        year
    )

    if not source.exists():

        raise FileNotFoundError(
            f"Roster input not found: {source}"
        )

    roster = load_json(
        source
    )

    (
        recruiting_records,
        loaded_years,
    ) = load_recruiting_history(
        year
    )

    if not recruiting_records:

        raise FileNotFoundError(
            "No recruiting history was available."
        )

    recruiting_index = (
        build_recruiting_index(
            recruiting_records
        )
    )

    teams = {}

    for player in roster:

        team = player.get(
            "team"
        )

        if not team:
            continue

        if team not in teams:

            teams[
                team
            ] = create_team_profile(
                team,
                year
            )

        recruiting_record = (
            find_recruiting_record(
                player,
                recruiting_index
            )
        )

        add_roster_player(
            teams[
                team
            ],
            player,
            recruiting_record
        )

    processed = []

    for profile in teams.values():

        processed.append(
            finalize_team_profile(
                profile
            )
        )

    processed.sort(
        key=lambda team:
            team[
                "team"
            ]
    )

    destination = output_file(
        year
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
            processed,
            file,
            indent=4
        )

    total_roster_players = sum(
        team[
            "roster_size"
        ]
        for team in processed
    )

    total_matched = sum(
        team[
            "matched_recruiting_players"
        ]
        for team in processed
    )

    total_rated = sum(
        team[
            "rated_players"
        ]
        for team in processed
    )

    print("=" * 78)

    print(
        f"{year} TEAM TALENT COMPOSITION"
    )

    print("=" * 78)

    print(
        "Recruiting classes loaded: "
        + ", ".join(
            str(value)
            for value in loaded_years
        )
    )

    print(
        f"Recruiting records available: "
        f"{len(recruiting_records)}"
    )

    print(
        f"Teams processed: "
        f"{len(processed)}"
    )

    print(
        f"Roster players: "
        f"{total_roster_players}"
    )

    print(
        f"Players matched to recruiting history: "
        f"{total_matched}"
    )

    print(
        f"Players with ratings: "
        f"{total_rated}"
    )

    if total_roster_players:

        print(
            f"Overall roster rating coverage: "
            f"{total_rated / total_roster_players * 100:.1f}%"
        )

    print()

    print(
        "TOP 15 BY BLUE-CHIP PERCENTAGE"
    )

    print("-" * 78)

    blue_chip_rank = sorted(
        [
            team
            for team in processed
            if team[
                "rated_players"
            ] >= 20
        ],
        key=lambda team:
            (
                team[
                    "blue_chip_percentage"
                ],
                team[
                    "top_20_average_rating"
                ],
            ),
        reverse=True,
    )

    for team in blue_chip_rank[:15]:

        print(
            f"{team['team']}: "
            f"blue_chip="
            f"{team['blue_chip_percentage'] * 100:.1f}%, "
            f"blue_chips="
            f"{team['blue_chip_count']}, "
            f"elite="
            f"{team['elite_count']}, "
            f"avg="
            f"{team['average_rating']:.4f}, "
            f"top20="
            f"{team['top_20_average_rating']:.4f}"
        )

    print()

    print(
        "TOP 15 BY TOP-20 ROSTER TALENT"
    )

    print("-" * 78)

    top_20_rank = sorted(
        [
            team
            for team in processed
            if team[
                "rated_players"
            ] >= 20
        ],
        key=lambda team:
            team[
                "top_20_average_rating"
            ],
        reverse=True,
    )

    for team in top_20_rank[:15]:

        print(
            f"{team['team']}: "
            f"top20="
            f"{team['top_20_average_rating']:.4f}, "
            f"top10="
            f"{team['top_10_average_rating']:.4f}, "
            f"blue_chips="
            f"{team['blue_chip_count']}, "
            f"5-star="
            f"{team['five_star_count']}, "
            f"4-star="
            f"{team['four_star_count']}"
        )

    print()

    print(
        "TOP 15 BY ELITE PLAYER COUNT"
    )

    print("-" * 78)

    elite_rank = sorted(
        processed,
        key=lambda team:
            (
                team[
                    "elite_count"
                ],
                team[
                    "top_20_average_rating"
                ],
            ),
        reverse=True,
    )

    for team in elite_rank[:15]:

        print(
            f"{team['team']}: "
            f"elite="
            f"{team['elite_count']}, "
            f"blue_chips="
            f"{team['blue_chip_count']}, "
            f"top20="
            f"{team['top_20_average_rating']:.4f}, "
            f"coverage="
            f"{team['rating_coverage'] * 100:.1f}%"
        )

    print()

    print(
        "TOP POSITION-GROUP TALENT"
    )

    print("-" * 78)

    for group in [
        "QB",
        "SKILL",
        "OL",
        "DL",
        "LB",
        "DB",
    ]:

        candidates = [
            team
            for team in processed
            if team[
                "position_groups"
            ][
                group
            ][
                "rated_count"
            ] >= 2
        ]

        candidates.sort(
            key=lambda team:
                team[
                    "position_groups"
                ][
                    group
                ][
                    "average_rating"
                ],
            reverse=True,
        )

        if not candidates:
            continue

        leader = candidates[0]

        position = leader[
            "position_groups"
        ][
            group
        ]

        print(
            f"{group}: "
            f"{leader['team']} "
            f"avg="
            f"{position['average_rating']:.4f}, "
            f"rated="
            f"{position['rated_count']}, "
            f"blue_chips="
            f"{position['blue_chip_count']}"
        )

    print()

    print(
        f"Saved to {destination}"
    )


if __name__ == "__main__":

    year = 2024

    if len(sys.argv) > 1:

        year = int(
            sys.argv[1]
        )

    calculate_team_talent_composition(
        year
    )
