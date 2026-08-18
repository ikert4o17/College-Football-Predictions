"""
Project Gridiron
Transfer Production and Experience - Version 2

This version fixes an important issue discovered in V1:

CFBD player usage / PPA fields should NOT be interpreted identically
for every position.

V2 therefore separates transfer production by position group.

Usage:
    python -m ratings.transfer_production_v2 2025
    python -m ratings.transfer_production_v2 2026

Historical example:
    target season = 2025
    prior production season = 2024

Inputs:
    data/processed/enriched_transfer_portal_<target_year>.json

    data/raw/qb_data/<previous_year>/player_usage.json
    data/raw/qb_data/<previous_year>/player_ppa.json
    data/raw/qb_data/<previous_year>/roster.json

Output:
    data/processed/transfer_production_v2_<target_year>.json

POSITION RULES

QB:
    passing usage
    passing PPA
    total passing PPA

RB / WR / TE:
    offensive usage
    overall PPA
    total PPA

OL:
    no PPA-based production score
    match / experience information retained only

DEFENSE:
    no offensive PPA-based production score
    match / experience information retained only

ALL PLAYERS:
    transfer talent rating retained
    prior-season match coverage tracked explicitly

This module does NOT modify production power ratings.
"""

import json
import re
import sys
import unicodedata
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# POSITION GROUPS
# ============================================================

QB_POSITIONS = {
    "QB",
    "QUARTERBACK",
}

RB_POSITIONS = {
    "RB",
    "HB",
    "FB",
    "RUNNING BACK",
}

WR_POSITIONS = {
    "WR",
    "WIDE RECEIVER",
}

TE_POSITIONS = {
    "TE",
    "TIGHT END",
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
    "CENTER",
    "OFFENSIVE LINE",
    "OFFENSIVE TACKLE",
    "OFFENSIVE GUARD",
}

DEFENSIVE_POSITIONS = {
    "DL",
    "DT",
    "NT",
    "DE",
    "EDGE",

    "LB",
    "ILB",
    "OLB",
    "MLB",

    "DB",
    "CB",
    "S",
    "FS",
    "SS",

    "DEFENSIVE LINE",
    "DEFENSIVE TACKLE",
    "DEFENSIVE END",
    "LINEBACKER",
    "CORNERBACK",
    "SAFETY",
}

SPECIAL_TEAMS_POSITIONS = {
    "K",
    "P",
    "LS",
    "PK",
    "PUNTER",
    "KICKER",
    "LONG SNAPPER",
}


# ============================================================
# MODEL / DIAGNOSTIC THRESHOLDS
# ============================================================

HIGH_END_TALENT = 0.9000

QB_HIGH_PASS_USAGE = 0.70
QB_PRODUCTIVE_PPA = 0.20

SKILL_HIGH_USAGE = 0.30
SKILL_PRODUCTIVE_PPA = 0.15


# ============================================================
# PATHS
# ============================================================

def transfer_file(target_year):
    """Return enriched portal file."""

    return (
        PROJECT_ROOT
        / "data"
        / "processed"
        / f"enriched_transfer_portal_{target_year}.json"
    )


def player_directory(target_year):
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
        / f"transfer_production_v2_{target_year}.json"
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


def normalize_text(value):
    """Normalize names and schools."""

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


def player_name(record):
    """Return transfer player name."""

    existing = record.get(
        "player"
    )

    if existing:
        return str(
            existing
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
# POSITION CLASSIFICATION
# ============================================================

def classify_position(position):
    """Return broad position group."""

    position = normalize_position(
        position
    )

    if position in QB_POSITIONS:
        return "QB"

    if position in RB_POSITIONS:
        return "RB"

    if position in WR_POSITIONS:
        return "WR"

    if position in TE_POSITIONS:
        return "TE"

    if position in OL_POSITIONS:
        return "OL"

    if position in DEFENSIVE_POSITIONS:
        return "DEFENSE"

    if position in SPECIAL_TEAMS_POSITIONS:
        return "SPECIAL_TEAMS"

    return "OTHER"


def is_skill_position(group):
    """Return whether offensive skill PPA is meaningful."""

    return group in {
        "RB",
        "WR",
        "TE",
    }


# ============================================================
# USAGE / PPA HELPERS
# ============================================================

def get_overall_usage(record):
    """Read overall usage."""

    return safe_float(
        record.get(
            "usage",
            {}
        ).get(
            "overall"
        )
    )


def get_pass_usage(record):
    """Read passing usage."""

    return safe_float(
        record.get(
            "usage",
            {}
        ).get(
            "pass"
        )
    )


def get_rush_usage(record):
    """Read rushing usage."""

    return safe_float(
        record.get(
            "usage",
            {}
        ).get(
            "rush"
        )
    )


def get_average_ppa(record):
    """Read overall average PPA."""

    return safe_float(
        record.get(
            "averagePPA",
            {}
        ).get(
            "all"
        )
    )


def get_total_ppa(record):
    """Read overall total PPA."""

    return safe_float(
        record.get(
            "totalPPA",
            {}
        ).get(
            "all"
        )
    )


def get_average_pass_ppa(record):
    """Read average passing PPA."""

    return safe_float(
        record.get(
            "averagePPA",
            {}
        ).get(
            "pass"
        )
    )


def get_total_pass_ppa(record):
    """Read total passing PPA."""

    return safe_float(
        record.get(
            "totalPPA",
            {}
        ).get(
            "pass"
        )
    )


# ============================================================
# PRIOR-SEASON PLAYER INDEX
# ============================================================

def build_player_index(
    usage_records,
    ppa_records,
    roster_records
):
    """Build prior-season player index."""

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

        position = normalize_position(
            usage.get(
                "position"
            )
        )

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
                position,

            "position_group":
                classify_position(
                    position
                ),

            "usage":
                usage,

            "ppa":
                ppa_by_id.get(
                    player_id,
                    {}
                ),

            "roster":
                roster_by_id.get(
                    player_id,
                    {}
                ),
        }

        exact_index.setdefault(
            (
                name,
                team,
            ),
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
# PLAYER MATCHING
# ============================================================

def choose_candidate(
    candidates,
    transfer_position
):
    """Choose best conservative candidate."""

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    transfer_group = classify_position(
        transfer_position
    )

    group_matches = [
        player
        for player in candidates
        if player[
            "position_group"
        ] == transfer_group
    ]

    if len(group_matches) == 1:
        return group_matches[0]

    pool = (
        group_matches
        if group_matches
        else candidates
    )

    pool = sorted(
        pool,
        key=lambda player:
            get_overall_usage(
                player[
                    "usage"
                ]
            ),
        reverse=True,
    )

    return (
        pool[0]
        if pool
        else None
    )


def match_player(
    transfer,
    index
):
    """Match transfer to prior-season player."""

    name = normalize_text(
        player_name(
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

    exact = index[
        "exact"
    ].get(
        (
            name,
            origin,
        ),
        []
    )

    if exact:

        return (
            choose_candidate(
                exact,
                position
            ),
            "name_origin"
        )

    name_matches = index[
        "name"
    ].get(
        name,
        []
    )

    if len(name_matches) == 1:

        return (
            name_matches[0],
            "unique_name"
        )

    if name_matches:

        candidate = choose_candidate(
            name_matches,
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
# PLAYER-LEVEL PRODUCTION RECORD
# ============================================================

def build_transfer_record(
    transfer,
    previous_player,
    match_method
):
    """Build clean position-aware transfer record."""

    position = normalize_position(
        transfer.get(
            "position"
        )
    )

    group = classify_position(
        position
    )

    talent = transfer.get(
        "talent",
        {}
    )

    rating = safe_float(
        talent.get(
            "effective_rating"
        )
    )

    base = {
        "player":
            player_name(
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

        "position_group":
            group,

        "effective_rating":
            rating,

        "high_end_talent":
            rating
            >= HIGH_END_TALENT,

        "matched":
            previous_player
            is not None,

        "match_method":
            match_method,

        "previous_player_id":
            None,

        "previous_team":
            None,

        "class_year":
            None,

        "overall_usage":
            None,

        "pass_usage":
            None,

        "rush_usage":
            None,

        "average_ppa":
            None,

        "total_ppa":
            None,

        "average_pass_ppa":
            None,

        "total_pass_ppa":
            None,

        "production_metric_available":
            False,

        "production_type":
            "none",

        "productive_player":
            False,
    }

    if not previous_player:

        return base

    usage = previous_player[
        "usage"
    ]

    ppa = previous_player[
        "ppa"
    ]

    roster = previous_player[
        "roster"
    ]

    base[
        "previous_player_id"
    ] = previous_player[
        "id"
    ]

    base[
        "previous_team"
    ] = previous_player[
        "team"
    ]

    base[
        "class_year"
    ] = roster.get(
        "year"
    )

    # ------------------------------------------------------------
    # QB
    # ------------------------------------------------------------

    if group == "QB":

        pass_usage = get_pass_usage(
            usage
        )

        average_pass_ppa = (
            get_average_pass_ppa(
                ppa
            )
        )

        total_pass_ppa = (
            get_total_pass_ppa(
                ppa
            )
        )

        base[
            "pass_usage"
        ] = pass_usage

        base[
            "average_pass_ppa"
        ] = average_pass_ppa

        base[
            "total_pass_ppa"
        ] = total_pass_ppa

        base[
            "production_metric_available"
        ] = True

        base[
            "production_type"
        ] = "qb_passing"

        base[
            "productive_player"
        ] = (
            pass_usage
            >= QB_HIGH_PASS_USAGE
            and
            average_pass_ppa
            >= QB_PRODUCTIVE_PPA
        )

        return base

    # ------------------------------------------------------------
    # RB / WR / TE
    # ------------------------------------------------------------

    if is_skill_position(
        group
    ):

        overall_usage = get_overall_usage(
            usage
        )

        rush_usage = get_rush_usage(
            usage
        )

        average_ppa = get_average_ppa(
            ppa
        )

        total_ppa = get_total_ppa(
            ppa
        )

        base[
            "overall_usage"
        ] = overall_usage

        base[
            "rush_usage"
        ] = rush_usage

        base[
            "average_ppa"
        ] = average_ppa

        base[
            "total_ppa"
        ] = total_ppa

        base[
            "production_metric_available"
        ] = True

        base[
            "production_type"
        ] = "skill_offense"

        base[
            "productive_player"
        ] = (
            overall_usage
            >= SKILL_HIGH_USAGE
            and
            average_ppa
            >= SKILL_PRODUCTIVE_PPA
        )

        return base

    # ------------------------------------------------------------
    # OL / DEFENSE / SPECIAL TEAMS / OTHER
    # ------------------------------------------------------------

    base[
        "production_type"
    ] = "experience_only"

    return base


# ============================================================
# TEAM AGGREGATION
# ============================================================

def create_side():
    """Create empty side profile."""

    return {
        "transfer_count": 0,

        "matched_count": 0,

        "unmatched_count": 0,

        "production_available_count": 0,

        "high_end_talent_count": 0,

        "productive_player_count": 0,

        "qb_count": 0,

        "qb_matched_count": 0,

        "productive_qb_count": 0,

        "qb_pass_usage_sum": 0.0,

        "qb_total_pass_ppa_sum": 0.0,

        "qb_average_pass_ppa_sum": 0.0,

        "skill_count": 0,

        "skill_matched_count": 0,

        "productive_skill_count": 0,

        "skill_usage_sum": 0.0,

        "skill_total_ppa_sum": 0.0,

        "skill_average_ppa_sum": 0.0,

        "ol_count": 0,

        "ol_matched_count": 0,

        "defense_count": 0,

        "defense_matched_count": 0,

        "special_teams_count": 0,

        "other_count": 0,

        "talent_weighted_productive_count":
            0.0,

        "qb_talent_production_score":
            0.0,

        "skill_talent_production_score":
            0.0,
    }


def create_team(
    team,
    target_year
):
    """Create empty team profile."""

    return {
        "season":
            target_year,

        "team":
            team,

        "incoming":
            create_side(),

        "outgoing":
            create_side(),

        "net":
            {},
    }


def ensure_team(
    profiles,
    team,
    target_year
):
    """Create team if missing."""

    if not team:
        return

    if team not in profiles:

        profiles[
            team
        ] = create_team(
            team,
            target_year
        )


def add_to_side(
    side,
    player
):
    """Aggregate player into side profile."""

    side[
        "transfer_count"
    ] += 1

    if player[
        "high_end_talent"
    ]:

        side[
            "high_end_talent_count"
        ] += 1

    if player[
        "matched"
    ]:

        side[
            "matched_count"
        ] += 1

    else:

        side[
            "unmatched_count"
        ] += 1

    if player[
        "production_metric_available"
    ]:

        side[
            "production_available_count"
        ] += 1

    if player[
        "productive_player"
    ]:

        side[
            "productive_player_count"
        ] += 1

        side[
            "talent_weighted_productive_count"
        ] += player[
            "effective_rating"
        ]

    group = player[
        "position_group"
    ]

    # ------------------------------------------------------------
    # QB
    # ------------------------------------------------------------

    if group == "QB":

        side[
            "qb_count"
        ] += 1

        if player[
            "matched"
        ]:

            side[
                "qb_matched_count"
            ] += 1

        if player[
            "production_metric_available"
        ]:

            pass_usage = (
                player[
                    "pass_usage"
                ]
                or 0.0
            )

            total_pass_ppa = (
                player[
                    "total_pass_ppa"
                ]
                or 0.0
            )

            avg_pass_ppa = (
                player[
                    "average_pass_ppa"
                ]
                or 0.0
            )

            side[
                "qb_pass_usage_sum"
            ] += pass_usage

            side[
                "qb_total_pass_ppa_sum"
            ] += total_pass_ppa

            side[
                "qb_average_pass_ppa_sum"
            ] += avg_pass_ppa

            side[
                "qb_talent_production_score"
            ] += (
                player[
                    "effective_rating"
                ]
                *
                pass_usage
                *
                avg_pass_ppa
            )

        if player[
            "productive_player"
        ]:

            side[
                "productive_qb_count"
            ] += 1

        return

    # ------------------------------------------------------------
    # SKILL
    # ------------------------------------------------------------

    if is_skill_position(
        group
    ):

        side[
            "skill_count"
        ] += 1

        if player[
            "matched"
        ]:

            side[
                "skill_matched_count"
            ] += 1

        if player[
            "production_metric_available"
        ]:

            usage = (
                player[
                    "overall_usage"
                ]
                or 0.0
            )

            total_ppa = (
                player[
                    "total_ppa"
                ]
                or 0.0
            )

            avg_ppa = (
                player[
                    "average_ppa"
                ]
                or 0.0
            )

            side[
                "skill_usage_sum"
            ] += usage

            side[
                "skill_total_ppa_sum"
            ] += total_ppa

            side[
                "skill_average_ppa_sum"
            ] += avg_ppa

            side[
                "skill_talent_production_score"
            ] += (
                player[
                    "effective_rating"
                ]
                *
                usage
                *
                avg_ppa
            )

        if player[
            "productive_player"
        ]:

            side[
                "productive_skill_count"
            ] += 1

        return

    # ------------------------------------------------------------
    # OL
    # ------------------------------------------------------------

    if group == "OL":

        side[
            "ol_count"
        ] += 1

        if player[
            "matched"
        ]:

            side[
                "ol_matched_count"
            ] += 1

        return

    # ------------------------------------------------------------
    # DEFENSE
    # ------------------------------------------------------------

    if group == "DEFENSE":

        side[
            "defense_count"
        ] += 1

        if player[
            "matched"
        ]:

            side[
                "defense_matched_count"
            ] += 1

        return

    if group == "SPECIAL_TEAMS":

        side[
            "special_teams_count"
        ] += 1

        return

    side[
        "other_count"
    ] += 1


def round_side(side):
    """Round aggregate floats."""

    float_fields = [
        "qb_pass_usage_sum",
        "qb_total_pass_ppa_sum",
        "qb_average_pass_ppa_sum",
        "skill_usage_sum",
        "skill_total_ppa_sum",
        "skill_average_ppa_sum",
        "talent_weighted_productive_count",
        "qb_talent_production_score",
        "skill_talent_production_score",
    ]

    for field in float_fields:

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
    """Calculate net metrics."""

    incoming = round_side(
        profile[
            "incoming"
        ]
    )

    outgoing = round_side(
        profile[
            "outgoing"
        ]
    )

    profile[
        "net"
    ] = {
        "productive_player_count":
            incoming[
                "productive_player_count"
            ]
            -
            outgoing[
                "productive_player_count"
            ],

        "productive_qb_count":
            incoming[
                "productive_qb_count"
            ]
            -
            outgoing[
                "productive_qb_count"
            ],

        "productive_skill_count":
            incoming[
                "productive_skill_count"
            ]
            -
            outgoing[
                "productive_skill_count"
            ],

        "qb_pass_usage_sum":
            round(
                incoming[
                    "qb_pass_usage_sum"
                ]
                -
                outgoing[
                    "qb_pass_usage_sum"
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

        "skill_usage_sum":
            round(
                incoming[
                    "skill_usage_sum"
                ]
                -
                outgoing[
                    "skill_usage_sum"
                ],
                4
            ),

        "skill_total_ppa_sum":
            round(
                incoming[
                    "skill_total_ppa_sum"
                ]
                -
                outgoing[
                    "skill_total_ppa_sum"
                ],
                4
            ),

        "qb_talent_production_score":
            round(
                incoming[
                    "qb_talent_production_score"
                ]
                -
                outgoing[
                    "qb_talent_production_score"
                ],
                4
            ),

        "skill_talent_production_score":
            round(
                incoming[
                    "skill_talent_production_score"
                ]
                -
                outgoing[
                    "skill_talent_production_score"
                ],
                4
            ),

        "talent_weighted_productive_count":
            round(
                incoming[
                    "talent_weighted_productive_count"
                ]
                -
                outgoing[
                    "talent_weighted_productive_count"
                ],
                4
            ),
    }

    return profile


# ============================================================
# MAIN
# ============================================================

def calculate_transfer_production_v2(
    target_year
):
    """Build clean position-aware transfer production data."""

    previous_year = (
        target_year
        -
        1
    )

    portal_path = transfer_file(
        target_year
    )

    directory = player_directory(
        target_year
    )

    usage_path = (
        directory
        / "player_usage.json"
    )

    ppa_path = (
        directory
        / "player_ppa.json"
    )

    roster_path = (
        directory
        / "roster.json"
    )

    for path in [
        portal_path,
        usage_path,
        ppa_path,
        roster_path,
    ]:

        if not path.exists():

            raise FileNotFoundError(
                f"Transfer production V2 input missing: "
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

    index = build_player_index(
        usage_records,
        ppa_records,
        roster_records
    )

    player_records = []

    match_counts = {}

    position_counts = {}

    matched_position_counts = {}

    for transfer in transfers:

        previous_player, match_method = (
            match_player(
                transfer,
                index
            )
        )

        player = build_transfer_record(
            transfer,
            previous_player,
            match_method
        )

        player_records.append(
            player
        )

        match_counts[
            match_method
        ] = (
            match_counts.get(
                match_method,
                0
            )
            + 1
        )

        group = player[
            "position_group"
        ]

        position_counts[
            group
        ] = (
            position_counts.get(
                group,
                0
            )
            + 1
        )

        if player[
            "matched"
        ]:

            matched_position_counts[
                group
            ] = (
                matched_position_counts.get(
                    group,
                    0
                )
                + 1
            )

    profiles = {}

    for player in player_records:

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

            add_to_side(
                profiles[
                    origin
                ][
                    "outgoing"
                ],
                player
            )

        if destination:

            add_to_side(
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

    total_matched = sum(
        1
        for player in player_records
        if player[
            "matched"
        ]
    )

    production_available = sum(
        1
        for player in player_records
        if player[
            "production_metric_available"
        ]
    )

    print("=" * 78)

    print(
        f"{target_year} TRANSFER PRODUCTION + EXPERIENCE V2"
    )

    print("=" * 78)

    print(
        f"Prior production season: "
        f"{previous_year}"
    )

    print(
        f"Transfer records: "
        f"{len(transfers)}"
    )

    print(
        f"Transfers matched to prior-season player data: "
        f"{total_matched}"
    )

    if transfers:

        print(
            f"Overall match rate: "
            f"{total_matched / len(transfers) * 100:.1f}%"
        )

    print(
        f"Transfers with valid position-specific "
        f"production metric: "
        f"{production_available}"
    )

    print()

    print(
        "MATCH METHODS"
    )

    print("-" * 78)

    for method, count in sorted(
        match_counts.items(),
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
        "POSITION GROUP COVERAGE"
    )

    print("-" * 78)

    ordered_groups = [
        "QB",
        "RB",
        "WR",
        "TE",
        "OL",
        "DEFENSE",
        "SPECIAL_TEAMS",
        "OTHER",
    ]

    for group in ordered_groups:

        total = position_counts.get(
            group,
            0
        )

        matched = matched_position_counts.get(
            group,
            0
        )

        rate = (
            matched
            /
            total
            *
            100
            if total
            else 0.0
        )

        print(
            f"{group}: "
            f"{matched}/{total} matched "
            f"({rate:.1f}%)"
        )

    print()

    print(
        "TOP 15 INCOMING PRODUCTIVE QB TRANSFERS"
    )

    print("-" * 78)

    qb_players = [
        player
        for player in player_records
        if (
            player[
                "destination"
            ]
            and
            player[
                "position_group"
            ]
            == "QB"
            and
            player[
                "production_metric_available"
            ]
        )
    ]

    qb_players.sort(
        key=lambda player:
            player[
                "total_pass_ppa"
            ]
            or 0.0,
        reverse=True,
    )

    for player in qb_players[:15]:

        print(
            f"{player['player']}: "
            f"{player['origin']} -> "
            f"{player['destination']}, "
            f"pass_usage="
            f"{player['pass_usage']:.3f}, "
            f"avg_pass_PPA="
            f"{player['average_pass_ppa']:+.3f}, "
            f"total_pass_PPA="
            f"{player['total_pass_ppa']:+.1f}, "
            f"talent="
            f"{player['effective_rating']:.4f}"
        )

    print()

    print(
        "TOP 15 INCOMING PRODUCTIVE SKILL TRANSFERS"
    )

    print("-" * 78)

    skill_players = [
        player
        for player in player_records
        if (
            player[
                "destination"
            ]
            and
            is_skill_position(
                player[
                    "position_group"
                ]
            )
            and
            player[
                "production_metric_available"
            ]
        )
    ]

    skill_players.sort(
        key=lambda player:
            player[
                "total_ppa"
            ]
            or 0.0,
        reverse=True,
    )

    for player in skill_players[:15]:

        print(
            f"{player['player']}: "
            f"{player['origin']} -> "
            f"{player['destination']}, "
            f"pos="
            f"{player['position_group']}, "
            f"usage="
            f"{player['overall_usage']:.3f}, "
            f"avg_PPA="
            f"{player['average_ppa']:+.3f}, "
            f"total_PPA="
            f"{player['total_ppa']:+.1f}, "
            f"talent="
            f"{player['effective_rating']:.4f}"
        )

    print()

    print(
        "TOP 15 TEAMS BY NET PRODUCTIVE QB COUNT"
    )

    print("-" * 78)

    qb_teams = sorted(
        processed,
        key=lambda team:
            (
                team[
                    "net"
                ][
                    "productive_qb_count"
                ],
                team[
                    "net"
                ][
                    "qb_total_pass_ppa_sum"
                ],
            ),
        reverse=True,
    )

    for team in qb_teams[:15]:

        print(
            f"{team['team']}: "
            f"net_QBs="
            f"{team['net']['productive_qb_count']:+d}, "
            f"net_pass_PPA="
            f"{team['net']['qb_total_pass_ppa_sum']:+.1f}, "
            f"net_pass_usage="
            f"{team['net']['qb_pass_usage_sum']:+.3f}"
        )

    print()

    print(
        "TOP 15 TEAMS BY NET PRODUCTIVE SKILL COUNT"
    )

    print("-" * 78)

    skill_teams = sorted(
        processed,
        key=lambda team:
            (
                team[
                    "net"
                ][
                    "productive_skill_count"
                ],
                team[
                    "net"
                ][
                    "skill_total_ppa_sum"
                ],
            ),
        reverse=True,
    )

    for team in skill_teams[:15]:

        print(
            f"{team['team']}: "
            f"net_skill="
            f"{team['net']['productive_skill_count']:+d}, "
            f"net_skill_PPA="
            f"{team['net']['skill_total_ppa_sum']:+.1f}, "
            f"net_skill_usage="
            f"{team['net']['skill_usage_sum']:+.3f}"
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

    calculate_transfer_production_v2(
        target_year
    )
