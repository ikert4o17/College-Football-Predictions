"""
Project Gridiron
Transfer Production and Experience

Measure what transfer players actually did on the field before transferring.

Examples:

    python -m ratings.transfer_production 2025
    python -m ratings.transfer_production 2026

For target season 2025:
    transfer portal = 2025
    prior production = 2024

For target season 2026:
    transfer portal = 2026
    prior production = 2025

Inputs:
    data/processed/enriched_transfer_portal_<target_year>.json

    data/raw/qb_data/<previous_year>/player_usage.json
    data/raw/qb_data/<previous_year>/player_ppa.json
    data/raw/qb_data/<previous_year>/roster.json

NOTE:
The qb_data directory name is historical. Those files actually contain
ALL players returned by the CFBD player usage, PPA, and roster endpoints,
not only quarterbacks.

Output:
    data/processed/transfer_production_<target_year>.json

Primary goals:

- Distinguish proven transfers from highly rated but inexperienced players
- Measure incoming and outgoing prior usage
- Measure incoming and outgoing prior PPA
- Preserve transfer talent rating
- Identify experienced / productive QB transfers separately
- Build team-level metrics for later historical validation

This module does NOT modify production power ratings.
"""

import json
import re
import sys
import unicodedata
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# THRESHOLDS
# ============================================================

HIGH_USAGE_THRESHOLD = 0.40
VERY_HIGH_USAGE_THRESHOLD = 0.65

POSITIVE_PPA_THRESHOLD = 0.10
HIGH_PPA_THRESHOLD = 0.25

HIGH_END_TALENT_THRESHOLD = 0.90


# ============================================================
# PATHS
# ============================================================

def transfer_file(target_year):
    """Return enriched portal input for target season."""

    return (
        PROJECT_ROOT
        / "data"
        / "processed"
        / f"enriched_transfer_portal_{target_year}.json"
    )


def previous_player_directory(target_year):
    """Return prior-season player-data directory."""

    previous_year = (
        target_year
        -
        1
    )

    return (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "qb_data"
        / str(previous_year)
    )


def output_file(target_year):
    """Return output path."""

    return (
        PROJECT_ROOT
        / "data"
        / "processed"
        / f"transfer_production_{target_year}.json"
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
        return json.load(file)


def safe_float(value):
    """Safely convert a value to float."""

    if value is None:
        return 0.0

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return 0.0


def normalize_text(value):
    """Normalize text for conservative matching."""

    if not value:
        return ""

    value = unicodedata.normalize(
        "NFKD",
        str(value)
    )

    value = "".join(
        character
        for character in value
        if not unicodedata.combining(
            character
        )
    )

    value = value.lower()

    value = re.sub(
        r"[^a-z0-9\s]",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    ).strip()

    parts = value.split()

    suffixes = {
        "jr",
        "sr",
        "ii",
        "iii",
        "iv",
        "v",
    }

    while (
        parts
        and parts[-1] in suffixes
    ):
        parts.pop()

    return " ".join(
        parts
    )


def normalize_position(value):
    """Normalize position."""

    if not value:
        return "UNKNOWN"

    return (
        str(value)
        .strip()
        .upper()
    )


def transfer_player_name(record):
    """Get full player name from enriched portal record."""

    player = record.get(
        "player"
    )

    if player:
        return str(
            player
        ).strip()

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


# ============================================================
# CFBD PLAYER DATA
# ============================================================

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


def get_pass_usage(record):
    """Read pass usage."""

    usage = record.get(
        "usage",
        {}
    )

    return safe_float(
        usage.get(
            "pass"
        )
    )


def get_rush_usage(record):
    """Read rush usage."""

    usage = record.get(
        "usage",
        {}
    )

    return safe_float(
        usage.get(
            "rush"
        )
    )


def get_average_ppa(record):
    """Read average overall PPA."""

    average = record.get(
        "averagePPA",
        {}
    )

    return safe_float(
        average.get(
            "all"
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


def get_average_rush_ppa(record):
    """Read average rushing PPA."""

    average = record.get(
        "averagePPA",
        {}
    )

    return safe_float(
        average.get(
            "rush"
        )
    )


def get_total_ppa(record):
    """Read total overall PPA."""

    total = record.get(
        "totalPPA",
        {}
    )

    return safe_float(
        total.get(
            "all"
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


def get_total_rush_ppa(record):
    """Read total rushing PPA."""

    total = record.get(
        "totalPPA",
        {}
    )

    return safe_float(
        total.get(
            "rush"
        )
    )


# ============================================================
# PLAYER INDEX
# ============================================================

def build_player_index(
    usage_records,
    ppa_records,
    roster_records
):
    """
    Build prior-season player index.

    Primary match key:
        normalized name + normalized team

    Secondary lookup:
        normalized name only
    """

    ppa_by_id = {}

    for record in ppa_records:

        player_id = record.get(
            "id"
        )

        if player_id is None:
            continue

        ppa_by_id[
            str(player_id)
        ] = record

    roster_by_id = {}

    for record in roster_records:

        player_id = record.get(
            "id"
        )

        if player_id is None:
            continue

        roster_by_id[
            str(player_id)
        ] = record

    exact_index = {}
    name_index = {}

    for usage in usage_records:

        player_id = usage.get(
            "id"
        )

        if player_id is None:
            continue

        player_id = str(
            player_id
        )

        name = normalize_text(
            usage.get(
                "name"
            )
        )

        team = normalize_text(
            usage.get(
                "team"
            )
        )

        if not name:
            continue

        player = {
            "id":
                player_id,

            "name":
                usage.get(
                    "name"
                ),

            "team":
                usage.get(
                    "team"
                ),

            "position":
                normalize_position(
                    usage.get(
                        "position"
                    )
                ),

            "usage_record":
                usage,

            "ppa_record":
                ppa_by_id.get(
                    player_id,
                    {}
                ),

            "roster_record":
                roster_by_id.get(
                    player_id,
                    {}
                ),
        }

        exact_key = (
            name,
            team,
        )

        exact_index.setdefault(
            exact_key,
            []
        ).append(
            player
        )

        name_index.setdefault(
            name,
            []
        ).append(
            player
        )

    return {
        "exact":
            exact_index,

        "name":
            name_index,
    }


# ============================================================
# MATCHING
# ============================================================

def choose_candidate(
    candidates,
    transfer_position
):
    """Choose conservatively among multiple candidates."""

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    transfer_position = normalize_position(
        transfer_position
    )

    position_matches = [
        player
        for player in candidates
        if player[
            "position"
        ] == transfer_position
    ]

    if len(position_matches) == 1:
        return position_matches[0]

    # If several remain, use highest prior overall usage.
    pool = (
        position_matches
        if position_matches
        else candidates
    )

    pool = sorted(
        pool,
        key=lambda player:
            get_overall_usage(
                player[
                    "usage_record"
                ]
            ),
        reverse=True,
    )

    if not pool:
        return None

    return pool[0]


def match_transfer_to_previous_player(
    transfer,
    player_index
):
    """
    Match transfer to previous-season CFBD player production.

    Preferred:
        name + origin team

    Fallback:
        unique / best name match
    """

    name = normalize_text(
        transfer_player_name(
            transfer
        )
    )

    origin = normalize_text(
        transfer.get(
            "origin"
        )
    )

    position = transfer.get(
        "position"
    )

    if not name:
        return (
            None,
            "missing_name"
        )

    exact_candidates = (
        player_index[
            "exact"
        ].get(
            (
                name,
                origin,
            ),
            []
        )
    )

    if exact_candidates:

        return (
            choose_candidate(
                exact_candidates,
                position
            ),
            "name_origin"
        )

    name_candidates = (
        player_index[
            "name"
        ].get(
            name,
            []
        )
    )

    if len(name_candidates) == 1:

        return (
            name_candidates[0],
            "unique_name"
        )

    if name_candidates:

        candidate = choose_candidate(
            name_candidates,
            position
        )

        if candidate:

            return (
                candidate,
                "name_position_fallback"
            )

    return (
        None,
        "unmatched"
    )


# ============================================================
# ENRICH ONE TRANSFER
# ============================================================

def build_production_record(
    transfer,
    previous_player,
    match_method
):
    """Build prior-production record for one portal player."""

    talent = transfer.get(
        "talent",
        {}
    )

    effective_rating = safe_float(
        talent.get(
            "effective_rating"
        )
    )

    position = normalize_position(
        transfer.get(
            "position"
        )
    )

    if not previous_player:

        return {
            "player":
                transfer_player_name(
                    transfer
                ),

            "origin":
                transfer.get(
                    "origin"
                ),

            "destination":
                transfer.get(
                    "destination"
                ),

            "position":
                position,

            "effective_rating":
                effective_rating,

            "matched_previous_production":
                False,

            "match_method":
                match_method,

            "previous_player_id":
                None,

            "previous_team":
                None,

            "previous_class_year":
                None,

            "overall_usage":
                0.0,

            "pass_usage":
                0.0,

            "rush_usage":
                0.0,

            "average_ppa":
                0.0,

            "average_pass_ppa":
                0.0,

            "average_rush_ppa":
                0.0,

            "total_ppa":
                0.0,

            "total_pass_ppa":
                0.0,

            "total_rush_ppa":
                0.0,

            "high_usage":
                False,

            "very_high_usage":
                False,

            "positive_ppa":
                False,

            "high_ppa":
                False,

            "high_end_talent":
                (
                    effective_rating
                    >= HIGH_END_TALENT_THRESHOLD
                ),

            "is_qb":
                position
                in {
                    "QB",
                    "QUARTERBACK",
                },
        }

    usage = previous_player[
        "usage_record"
    ]

    ppa = previous_player[
        "ppa_record"
    ]

    roster = previous_player[
        "roster_record"
    ]

    overall_usage = get_overall_usage(
        usage
    )

    pass_usage = get_pass_usage(
        usage
    )

    rush_usage = get_rush_usage(
        usage
    )

    average_ppa = get_average_ppa(
        ppa
    )

    average_pass_ppa = (
        get_average_pass_ppa(
            ppa
        )
    )

    average_rush_ppa = (
        get_average_rush_ppa(
            ppa
        )
    )

    total_ppa = get_total_ppa(
        ppa
    )

    total_pass_ppa = (
        get_total_pass_ppa(
            ppa
        )
    )

    total_rush_ppa = (
        get_total_rush_ppa(
            ppa
        )
    )

    return {
        "player":
            transfer_player_name(
                transfer
            ),

        "origin":
            transfer.get(
                "origin"
            ),

        "destination":
            transfer.get(
                "destination"
            ),

        "position":
            position,

        "effective_rating":
            effective_rating,

        "matched_previous_production":
            True,

        "match_method":
            match_method,

        "previous_player_id":
            previous_player[
                "id"
            ],

        "previous_team":
            previous_player[
                "team"
            ],

        "previous_class_year":
            roster.get(
                "year"
            ),

        "overall_usage":
            overall_usage,

        "pass_usage":
            pass_usage,

        "rush_usage":
            rush_usage,

        "average_ppa":
            average_ppa,

        "average_pass_ppa":
            average_pass_ppa,

        "average_rush_ppa":
            average_rush_ppa,

        "total_ppa":
            total_ppa,

        "total_pass_ppa":
            total_pass_ppa,

        "total_rush_ppa":
            total_rush_ppa,

        "high_usage":
            (
                overall_usage
                >= HIGH_USAGE_THRESHOLD
            ),

        "very_high_usage":
            (
                overall_usage
                >= VERY_HIGH_USAGE_THRESHOLD
            ),

        "positive_ppa":
            (
                average_ppa
                >= POSITIVE_PPA_THRESHOLD
            ),

        "high_ppa":
            (
                average_ppa
                >= HIGH_PPA_THRESHOLD
            ),

        "high_end_talent":
            (
                effective_rating
                >= HIGH_END_TALENT_THRESHOLD
            ),

        "is_qb":
            position
            in {
                "QB",
                "QUARTERBACK",
            },
    }


# ============================================================
# TEAM AGGREGATION
# ============================================================

def create_side_profile():
    """Create empty incoming/outgoing production profile."""

    return {
        "count": 0,

        "matched_count": 0,

        "high_usage_count": 0,

        "very_high_usage_count": 0,

        "positive_ppa_count": 0,

        "high_ppa_count": 0,

        "high_end_talent_count": 0,

        "usage_sum": 0.0,

        "average_usage": 0.0,

        "average_ppa_sum": 0.0,

        "mean_average_ppa": 0.0,

        "total_ppa_sum": 0.0,

        "talent_weighted_usage_sum": 0.0,

        "production_weighted_talent_sum": 0.0,

        "qb_count": 0,

        "qb_matched_count": 0,

        "qb_usage_sum": 0.0,

        "qb_average_pass_ppa_sum": 0.0,

        "qb_total_pass_ppa_sum": 0.0,

        "productive_qb_count": 0,

        "positions": {},
    }


def create_team_profile(
    team,
    target_year
):
    """Create empty team production profile."""

    return {
        "season":
            target_year,

        "team":
            team,

        "incoming":
            create_side_profile(),

        "outgoing":
            create_side_profile(),

        "net": {},
    }


def ensure_team(
    profiles,
    team,
    target_year
):
    """Create team if needed."""

    if not team:
        return

    if team not in profiles:

        profiles[
            team
        ] = create_team_profile(
            team,
            target_year
        )


def add_player_to_side(
    side,
    player
):
    """Aggregate one transfer into incoming/outgoing profile."""

    side[
        "count"
    ] += 1

    position = player[
        "position"
    ]

    side[
        "positions"
    ][position] = (
        side[
            "positions"
        ].get(
            position,
            0
        )
        + 1
    )

    if player[
        "high_end_talent"
    ]:

        side[
            "high_end_talent_count"
        ] += 1

    if player[
        "is_qb"
    ]:

        side[
            "qb_count"
        ] += 1

    if not player[
        "matched_previous_production"
    ]:

        return

    side[
        "matched_count"
    ] += 1

    usage = player[
        "overall_usage"
    ]

    avg_ppa = player[
        "average_ppa"
    ]

    total_ppa = player[
        "total_ppa"
    ]

    talent = player[
        "effective_rating"
    ]

    side[
        "usage_sum"
    ] += usage

    side[
        "average_ppa_sum"
    ] += avg_ppa

    side[
        "total_ppa_sum"
    ] += total_ppa

    side[
        "talent_weighted_usage_sum"
    ] += (
        talent
        *
        usage
    )

    # Combines:
    # talent × actual role × actual efficiency.
    side[
        "production_weighted_talent_sum"
    ] += (
        talent
        *
        usage
        *
        avg_ppa
    )

    if player[
        "high_usage"
    ]:

        side[
            "high_usage_count"
        ] += 1

    if player[
        "very_high_usage"
    ]:

        side[
            "very_high_usage_count"
        ] += 1

    if player[
        "positive_ppa"
    ]:

        side[
            "positive_ppa_count"
        ] += 1

    if player[
        "high_ppa"
    ]:

        side[
            "high_ppa_count"
        ] += 1

    if player[
        "is_qb"
    ]:

        side[
            "qb_matched_count"
        ] += 1

        side[
            "qb_usage_sum"
        ] += player[
            "pass_usage"
        ]

        side[
            "qb_average_pass_ppa_sum"
        ] += player[
            "average_pass_ppa"
        ]

        side[
            "qb_total_pass_ppa_sum"
        ] += player[
            "total_pass_ppa"
        ]

        if (
            player[
                "pass_usage"
            ] >= 0.50
            and
            player[
                "average_pass_ppa"
            ] >= 0.10
        ):

            side[
                "productive_qb_count"
            ] += 1


def finalize_side(side):
    """Calculate averages and round output."""

    matched = side[
        "matched_count"
    ]

    if matched > 0:

        side[
            "average_usage"
        ] = (
            side[
                "usage_sum"
            ]
            /
            matched
        )

        side[
            "mean_average_ppa"
        ] = (
            side[
                "average_ppa_sum"
            ]
            /
            matched
        )

    numeric_fields = [
        "usage_sum",
        "average_usage",
        "average_ppa_sum",
        "mean_average_ppa",
        "total_ppa_sum",
        "talent_weighted_usage_sum",
        "production_weighted_talent_sum",
        "qb_usage_sum",
        "qb_average_pass_ppa_sum",
        "qb_total_pass_ppa_sum",
    ]

    for field in numeric_fields:

        side[
            field
        ] = round(
            side[
                field
            ],
            4
        )

    return side


def finalize_team(profile):
    """Build net team production metrics."""

    incoming = finalize_side(
        profile[
            "incoming"
        ]
    )

    outgoing = finalize_side(
        profile[
            "outgoing"
        ]
    )

    profile[
        "net"
    ] = {
        "matched_transfer_count":
            incoming[
                "matched_count"
            ]
            -
            outgoing[
                "matched_count"
            ],

        "high_usage_count":
            incoming[
                "high_usage_count"
            ]
            -
            outgoing[
                "high_usage_count"
            ],

        "very_high_usage_count":
            incoming[
                "very_high_usage_count"
            ]
            -
            outgoing[
                "very_high_usage_count"
            ],

        "positive_ppa_count":
            incoming[
                "positive_ppa_count"
            ]
            -
            outgoing[
                "positive_ppa_count"
            ],

        "high_ppa_count":
            incoming[
                "high_ppa_count"
            ]
            -
            outgoing[
                "high_ppa_count"
            ],

        "usage_sum":
            round(
                incoming[
                    "usage_sum"
                ]
                -
                outgoing[
                    "usage_sum"
                ],
                4
            ),

        "total_ppa_sum":
            round(
                incoming[
                    "total_ppa_sum"
                ]
                -
                outgoing[
                    "total_ppa_sum"
                ],
                4
            ),

        "talent_weighted_usage_sum":
            round(
                incoming[
                    "talent_weighted_usage_sum"
                ]
                -
                outgoing[
                    "talent_weighted_usage_sum"
                ],
                4
            ),

        "production_weighted_talent_sum":
            round(
                incoming[
                    "production_weighted_talent_sum"
                ]
                -
                outgoing[
                    "production_weighted_talent_sum"
                ],
                4
            ),

        "productive_qb_count":
            incoming[
                "productive_qb_count"
            ]
            -
            outgoing[
                "productive_qb_count"
            ],

        "qb_usage_sum":
            round(
                incoming[
                    "qb_usage_sum"
                ]
                -
                outgoing[
                    "qb_usage_sum"
                ],
                4
            ),

        "qb_total_pass_ppa_sum":
            round(
                incoming[
                    "qb_total_pass_ppa_sum"
                ]
                -
                outgoing[
                    "qb_total_pass_ppa_sum"
                ],
                4
            ),
    }

    return profile


# ============================================================
# MAIN
# ============================================================

def calculate_transfer_production(
    target_year
):
    """Build transfer production profiles for target season."""

    previous_year = (
        target_year
        -
        1
    )

    portal_path = transfer_file(
        target_year
    )

    player_directory = (
        previous_player_directory(
            target_year
        )
    )

    usage_path = (
        player_directory
        / "player_usage.json"
    )

    ppa_path = (
        player_directory
        / "player_ppa.json"
    )

    roster_path = (
        player_directory
        / "roster.json"
    )

    required_files = [
        portal_path,
        usage_path,
        ppa_path,
        roster_path,
    ]

    for path in required_files:

        if not path.exists():

            raise FileNotFoundError(
                f"Transfer production input missing: "
                f"{path}"
            )

    transfers = load_json(
        portal_path
    )

    usage_records = load_json(
        usage_path
    )

    ppa_records = load_json(
        ppa_path
    )

    roster_records = load_json(
        roster_path
    )

    player_index = build_player_index(
        usage_records,
        ppa_records,
        roster_records
    )

    enriched_players = []

    match_methods = {}

    for transfer in transfers:

        (
            previous_player,
            match_method,
        ) = match_transfer_to_previous_player(
            transfer,
            player_index
        )

        player = build_production_record(
            transfer,
            previous_player,
            match_method
        )

        enriched_players.append(
            player
        )

        match_methods[
            match_method
        ] = (
            match_methods.get(
                match_method,
                0
            )
            + 1
        )

    profiles = {}

    for player in enriched_players:

        origin = player[
            "origin"
        ]

        destination = player[
            "destination"
        ]

        ensure_team(
            profiles,
            origin,
            target_year
        )

        ensure_team(
            profiles,
            destination,
            target_year
        )

        if origin:

            add_player_to_side(
                profiles[
                    origin
                ][
                    "outgoing"
                ],
                player
            )

        if destination:

            add_player_to_side(
                profiles[
                    destination
                ][
                    "incoming"
                ],
                player
            )

    processed = []

    for profile in profiles.values():

        processed.append(
            finalize_team(
                profile
            )
        )

    processed.sort(
        key=lambda team:
            team[
                "team"
            ]
    )

    destination_path = output_file(
        target_year
    )

    destination_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with destination_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            processed,
            file,
            indent=4
        )

    matched_players = [
        player
        for player in enriched_players
        if player[
            "matched_previous_production"
        ]
    ]

    productive_incoming = sorted(
        [
            player
            for player in enriched_players
            if (
                player[
                    "destination"
                ]
                and
                player[
                    "matched_previous_production"
                ]
            )
        ],
        key=lambda player:
            player[
                "total_ppa"
            ],
        reverse=True,
    )

    productive_qbs = sorted(
        [
            player
            for player in enriched_players
            if (
                player[
                    "destination"
                ]
                and
                player[
                    "is_qb"
                ]
                and
                player[
                    "matched_previous_production"
                ]
            )
        ],
        key=lambda player:
            player[
                "total_pass_ppa"
            ],
        reverse=True,
    )

    print("=" * 76)

    print(
        f"{target_year} TRANSFER PRODUCTION + EXPERIENCE"
    )

    print("=" * 76)

    print(
        f"Prior production season: "
        f"{previous_year}"
    )

    print(
        f"Transfer records: "
        f"{len(transfers)}"
    )

    print(
        f"Transfers matched to prior production: "
        f"{len(matched_players)}"
    )

    if transfers:

        print(
            f"Prior-production match rate: "
            f"{len(matched_players) / len(transfers) * 100:.1f}%"
        )

    print(
        f"Team profiles created: "
        f"{len(processed)}"
    )

    print()

    print(
        "MATCH METHODS"
    )

    print("-" * 76)

    for (
        method,
        count
    ) in sorted(
        match_methods.items(),
        key=lambda item:
            item[1],
        reverse=True,
    ):

        print(
            f"{method}: "
            f"{count}"
        )

    print()

    print(
        "TOP 15 INCOMING TRANSFERS BY PRIOR TOTAL PPA"
    )

    print("-" * 76)

    for player in productive_incoming[:15]:

        print(
            f"{player['player']}: "
            f"{player['origin']} -> "
            f"{player['destination']}, "
            f"pos={player['position']}, "
            f"usage={player['overall_usage']:.3f}, "
            f"avg_PPA={player['average_ppa']:+.3f}, "
            f"total_PPA={player['total_ppa']:+.1f}, "
            f"talent={player['effective_rating']:.4f}"
        )

    print()

    print(
        "TOP 15 INCOMING QB TRANSFERS BY PRIOR PASS PPA"
    )

    print("-" * 76)

    for player in productive_qbs[:15]:

        print(
            f"{player['player']}: "
            f"{player['origin']} -> "
            f"{player['destination']}, "
            f"pass_usage={player['pass_usage']:.3f}, "
            f"avg_pass_PPA="
            f"{player['average_pass_ppa']:+.3f}, "
            f"total_pass_PPA="
            f"{player['total_pass_ppa']:+.1f}, "
            f"talent={player['effective_rating']:.4f}"
        )

    print()

    print(
        "TOP 15 TEAMS BY NET PRIOR TRANSFER PPA"
    )

    print("-" * 76)

    strongest = sorted(
        processed,
        key=lambda team:
            team[
                "net"
            ][
                "total_ppa_sum"
            ],
        reverse=True,
    )

    for team in strongest[:15]:

        print(
            f"{team['team']}: "
            f"net_PPA="
            f"{team['net']['total_ppa_sum']:+.1f}, "
            f"net_usage="
            f"{team['net']['usage_sum']:+.3f}, "
            f"net_high_usage="
            f"{team['net']['high_usage_count']:+d}, "
            f"net_productive_QB="
            f"{team['net']['productive_qb_count']:+d}"
        )

    print()

    print(
        "BOTTOM 15 TEAMS BY NET PRIOR TRANSFER PPA"
    )

    print("-" * 76)

    weakest = sorted(
        processed,
        key=lambda team:
            team[
                "net"
            ][
                "total_ppa_sum"
            ]
    )

    for team in weakest[:15]:

        print(
            f"{team['team']}: "
            f"net_PPA="
            f"{team['net']['total_ppa_sum']:+.1f}, "
            f"net_usage="
            f"{team['net']['usage_sum']:+.3f}, "
            f"net_high_usage="
            f"{team['net']['high_usage_count']:+d}, "
            f"net_productive_QB="
            f"{team['net']['productive_qb_count']:+d}"
        )

    print()

    print(
        f"Saved to {destination_path}"
    )


if __name__ == "__main__":

    target_year = 2025

    if len(sys.argv) > 1:

        target_year = int(
            sys.argv[1]
        )

    calculate_transfer_production(
        target_year
    )
