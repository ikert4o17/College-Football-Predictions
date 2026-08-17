"""
Project Gridiron
2026 Preseason Power Ratings

Build the actual 2026 preseason rating from:

    2025 final SP+ baseline
        +
    2026 returning production
        +
    2026 roster / portal snap experience
        +
    2026 incoming elite transfer talent
        -
    2026 outgoing elite transfer talent

Recruiting is retained in the output for diagnostics, but the
historical V3 validation showed no incremental benefit from a
separate recruiting adjustment once SP+ and transfer talent were
already included.

Historical V3 evidence:

    SP+ baseline:
        correlation = 0.6429
        MAE = 8.65
        RMSE = 10.55

    SP+ + roster adjustments:
        correlation = 0.6607
        MAE = 8.52
        RMSE = 10.34

A lower-error V3 configuration suggested approximately:

    Returning production:
        +/- 1.00 point

    Incoming 0.90+ transfers:
        +0.75 points per player

    Outgoing 0.90+ transfers:
        -1.25 points per player

    Recruiting:
        0 independent points

The 2026 snap metric is new and has not been historically
validated. Therefore its effect is intentionally conservative.

This module DOES create the 2026 preseason rating file, but does
not overwrite the final 2025 power ratings.
"""

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# INPUT FILES
# ============================================================

SP_2025_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "sp_ratings"
    / "2025.json"
)

GRIDIRON_2025_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "power_ratings_2025.json"
)

RETURNING_2026_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "returning_production_2026.json"
)

TRANSFER_2026_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "transfer_talent_2026.json"
)

RECRUITING_2026_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "recruiting_talent_2026.json"
)

SNAPS_2026_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "returning_snaps"
    / "2026.json"
)


OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "preseason_ratings_2026.json"
)


# ============================================================
# MODEL PARAMETERS
# ============================================================

# Historical V3 result.
RETURNING_MAX_POINTS = 1.00

# Lower-error V3 transfer configuration.
INCOMING_ELITE_POINTS = 0.75
OUTGOING_ELITE_POINTS = 1.25

# Recruiting did not add incremental predictive value in V3.
RECRUITING_MAX_POINTS = 0.00

# Punt & Rally roster snap data is useful conceptually but
# does not yet have historical validation in our model.
#
# Keep this deliberately small until we have more seasons.
SNAP_MAX_POINTS = 0.50


RETURNING_CAP = 1.00
TRANSFER_CAP = 5.00
SNAP_CAP = 0.50


ELITE_TRANSFER_RATING = 0.90


# ============================================================
# GENERAL HELPERS
# ============================================================

def load_json(path):
    """Load JSON data."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def safe_float(value):
    """Safely convert a value to float."""

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return None


def mean(values):
    """Calculate arithmetic mean."""

    if not values:
        return 0.0

    return (
        sum(values)
        /
        len(values)
    )


def standard_deviation(values):
    """Calculate population standard deviation."""

    if not values:
        return 0.0

    average = mean(
        values
    )

    variance = (
        sum(
            (
                value
                -
                average
            )
            ** 2
            for value in values
        )
        /
        len(values)
    )

    return math.sqrt(
        variance
    )


def clamp(
    value,
    minimum,
    maximum
):
    """Clamp a value to a range."""

    return max(
        minimum,
        min(
            value,
            maximum
        )
    )


def build_lookup(records):
    """Build lookup by team."""

    return {
        record["team"]: record
        for record in records
        if record.get("team")
    }


def z_score(
    value,
    average,
    std
):
    """Standardize a value."""

    if std == 0:
        return 0.0

    return (
        value
        -
        average
    ) / std


# ============================================================
# INPUT VALIDATION
# ============================================================

def check_required_files():
    """Check that all required 2026 inputs exist."""

    required_files = [
        (
            "2025 SP+ ratings",
            SP_2025_FILE,
        ),
        (
            "2025 Project Gridiron ratings",
            GRIDIRON_2025_FILE,
        ),
        (
            "2026 returning production",
            RETURNING_2026_FILE,
        ),
        (
            "2026 transfer talent",
            TRANSFER_2026_FILE,
        ),
        (
            "2026 recruiting talent",
            RECRUITING_2026_FILE,
        ),
        (
            "2026 roster snap data",
            SNAPS_2026_FILE,
        ),
    ]

    missing = []

    for (
        description,
        path
    ) in required_files:

        if not path.exists():

            missing.append(
                (
                    description,
                    path,
                )
            )

    if missing:

        print("=" * 72)

        print(
            "2026 PRESEASON MODEL INPUTS MISSING"
        )

        print("=" * 72)

        print()

        for (
            description,
            path
        ) in missing:

            print(
                f"MISSING: {description}"
            )

            print(
                f"  {path}"
            )

        print()

        print(
            "The model will not substitute 2025 roster data "
            "for missing 2026 data."
        )

        return False

    return True


# ============================================================
# SNAP DATA
# ============================================================

def load_snap_records():
    """
    Load the manually captured Punt & Rally 2026 snap dataset.

    Supports either:

        [
            {...},
            {...}
        ]

    or:

        {
            "records": [...]
        }
    """

    data = load_json(
        SNAPS_2026_FILE
    )

    if isinstance(
        data,
        list
    ):
        return data

    if isinstance(
        data,
        dict
    ):

        records = data.get(
            "records"
        )

        if isinstance(
            records,
            list
        ):
            return records

    raise ValueError(
        "Unsupported 2026 snap JSON structure."
    )


def get_snap_percent(record):
    """Get the roster snap percentage."""

    if not record:
        return 0.0

    possible_keys = [
        "returning_snap_percent",
        "snapback_percent",
        "snap_percent",
        "percent",
    ]

    for key in possible_keys:

        value = safe_float(
            record.get(
                key
            )
        )

        if value is None:
            continue

        # Some versions store 74 rather than .74.
        if value > 1.0:
            value = (
                value
                /
                100.0
            )

        return value

    return 0.0


def get_snap_total(record):
    """Get total roster snaps represented by Punt & Rally."""

    if not record:
        return 0.0

    possible_keys = [
        "returning_snaps",
        "snaps",
        "total_snaps",
    ]

    for key in possible_keys:

        value = safe_float(
            record.get(
                key
            )
        )

        if value is not None:
            return value

    return 0.0


# ============================================================
# RETURNING PRODUCTION
# ============================================================

def get_returning_percent(record):
    """Read overall CFBD returning production percentage."""

    if not record:
        return 0.0

    overall = record.get(
        "overall",
        {}
    )

    value = safe_float(
        overall.get(
            "percent"
        )
    )

    if value is None:
        return 0.0

    return value


# ============================================================
# BUILD TEAM RECORDS
# ============================================================

def build_team_records():
    """Combine all 2026 model inputs."""

    sp_2025 = load_json(
        SP_2025_FILE
    )

    gridiron_2025 = load_json(
        GRIDIRON_2025_FILE
    )

    returning_2026 = load_json(
        RETURNING_2026_FILE
    )

    transfer_2026 = load_json(
        TRANSFER_2026_FILE
    )

    recruiting_2026 = load_json(
        RECRUITING_2026_FILE
    )

    snaps_2026 = load_snap_records()

    sp_lookup = build_lookup(
        sp_2025
    )

    gridiron_lookup = build_lookup(
        gridiron_2025
    )

    returning_lookup = build_lookup(
        returning_2026
    )

    transfer_lookup = build_lookup(
        transfer_2026
    )

    recruiting_lookup = build_lookup(
        recruiting_2026
    )

    snap_lookup = build_lookup(
        snaps_2026
    )

    teams = []

    for team_name in sorted(
        gridiron_lookup
    ):

        if team_name not in sp_lookup:
            continue

        sp_rating = safe_float(
            sp_lookup[
                team_name
            ].get(
                "rating"
            )
        )

        gridiron_rating = safe_float(
            gridiron_lookup[
                team_name
            ].get(
                "power_rating"
            )
        )

        if (
            sp_rating is None
            or gridiron_rating is None
        ):
            continue

        returning = returning_lookup.get(
            team_name,
            {}
        )

        transfer = transfer_lookup.get(
            team_name,
            {}
        )

        recruiting = recruiting_lookup.get(
            team_name,
            {}
        )

        snaps = snap_lookup.get(
            team_name,
            {}
        )

        incoming = transfer.get(
            "incoming",
            {}
        )

        outgoing = transfer.get(
            "outgoing",
            {}
        )

        teams.append(
            {
                "team":
                    team_name,

                "sp_2025":
                    sp_rating,

                "gridiron_2025":
                    gridiron_rating,

                "returning_percent":
                    get_returning_percent(
                        returning
                    ),

                "roster_snap_percent":
                    get_snap_percent(
                        snaps
                    ),

                "roster_snaps":
                    get_snap_total(
                        snaps
                    ),

                "incoming_high_end":
                    safe_float(
                        incoming.get(
                            "high_end_count"
                        )
                    )
                    or 0.0,

                "outgoing_high_end":
                    safe_float(
                        outgoing.get(
                            "high_end_count"
                        )
                    )
                    or 0.0,

                "incoming_average_rating":
                    safe_float(
                        incoming.get(
                            "average_rating"
                        )
                    )
                    or 0.0,

                "outgoing_average_rating":
                    safe_float(
                        outgoing.get(
                            "average_rating"
                        )
                    )
                    or 0.0,

                "four_star_count":
                    safe_float(
                        recruiting.get(
                            "four_star_count"
                        )
                    )
                    or 0.0,

                "top_10_recruiting":
                    safe_float(
                        recruiting.get(
                            "top_10_average_rating"
                        )
                    )
                    or 0.0,
            }
        )

    return teams


# ============================================================
# MODEL CONTEXT
# ============================================================

def calculate_context(teams):
    """Calculate population values used for scaling."""

    gridiron_values = [
        team[
            "gridiron_2025"
        ]
        for team in teams
    ]

    sp_values = [
        team[
            "sp_2025"
        ]
        for team in teams
    ]

    returning_values = [
        team[
            "returning_percent"
        ]
        for team in teams
    ]

    snap_values = [
        team[
            "roster_snap_percent"
        ]
        for team in teams
    ]

    return {
        "gridiron_mean":
            mean(
                gridiron_values
            ),

        "gridiron_std":
            standard_deviation(
                gridiron_values
            ),

        "sp_mean":
            mean(
                sp_values
            ),

        "sp_std":
            standard_deviation(
                sp_values
            ),

        "returning_mean":
            mean(
                returning_values
            ),

        "returning_std":
            standard_deviation(
                returning_values
            ),

        "snap_mean":
            mean(
                snap_values
            ),

        "snap_std":
            standard_deviation(
                snap_values
            ),
    }


# ============================================================
# BASELINE
# ============================================================

def map_sp_to_gridiron_scale(
    team,
    context
):
    """
    Map final 2025 SP+ onto Project Gridiron's rating scale.

    Historical validation showed SP+ was a stronger next-season
    anchor than Project Gridiron's prior-year rating.
    """

    standardized = z_score(
        team[
            "sp_2025"
        ],
        context[
            "sp_mean"
        ],
        context[
            "sp_std"
        ],
    )

    return (
        context[
            "gridiron_mean"
        ]
        +
        standardized
        *
        context[
            "gridiron_std"
        ]
    )


# ============================================================
# ADJUSTMENTS
# ============================================================

def calculate_returning_adjustment(
    team,
    context
):
    """Apply historically validated returning-production effect."""

    std = context[
        "returning_std"
    ]

    if std == 0:
        return 0.0

    standardized = (
        (
            team[
                "returning_percent"
            ]
            -
            context[
                "returning_mean"
            ]
        )
        /
        std
    )

    adjustment = (
        standardized
        *
        RETURNING_MAX_POINTS
    )

    return clamp(
        adjustment,
        -RETURNING_CAP,
        RETURNING_CAP
    )


def calculate_snap_adjustment(
    team,
    context
):
    """
    Apply conservative 2026 roster-snap adjustment.

    This metric includes the experienced snaps represented on
    the new roster, including portal experience in the captured
    Punt & Rally data.

    It has NOT been historically validated by Project Gridiron,
    so its maximum effect is only +/- 0.50 points.
    """

    std = context[
        "snap_std"
    ]

    if std == 0:
        return 0.0

    standardized = (
        (
            team[
                "roster_snap_percent"
            ]
            -
            context[
                "snap_mean"
            ]
        )
        /
        std
    )

    adjustment = (
        standardized
        *
        SNAP_MAX_POINTS
    )

    return clamp(
        adjustment,
        -SNAP_CAP,
        SNAP_CAP
    )


def calculate_incoming_transfer_adjustment(
    team
):
    """Bonus for incoming 0.90+ portal players."""

    adjustment = (
        team[
            "incoming_high_end"
        ]
        *
        INCOMING_ELITE_POINTS
    )

    return clamp(
        adjustment,
        0.0,
        TRANSFER_CAP
    )


def calculate_outgoing_transfer_adjustment(
    team
):
    """Penalty for outgoing 0.90+ portal players."""

    adjustment = (
        -team[
            "outgoing_high_end"
        ]
        *
        OUTGOING_ELITE_POINTS
    )

    return clamp(
        adjustment,
        -TRANSFER_CAP,
        0.0
    )


def calculate_recruiting_adjustment(
    team
):
    """
    Recruiting adjustment.

    Currently zero because V3 found no incremental value once
    SP+ and portal talent were already included.

    The data remains in the output for diagnostics.
    """

    return 0.0


# ============================================================
# PROJECT RATING
# ============================================================

def calculate_team_rating(
    team,
    context
):
    """Calculate one team's 2026 preseason rating."""

    baseline = map_sp_to_gridiron_scale(
        team,
        context
    )

    returning_adjustment = (
        calculate_returning_adjustment(
            team,
            context
        )
    )

    snap_adjustment = (
        calculate_snap_adjustment(
            team,
            context
        )
    )

    incoming_adjustment = (
        calculate_incoming_transfer_adjustment(
            team
        )
    )

    outgoing_adjustment = (
        calculate_outgoing_transfer_adjustment(
            team
        )
    )

    recruiting_adjustment = (
        calculate_recruiting_adjustment(
            team
        )
    )

    total_adjustment = (
        returning_adjustment
        +
        snap_adjustment
        +
        incoming_adjustment
        +
        outgoing_adjustment
        +
        recruiting_adjustment
    )

    preseason_rating = (
        baseline
        +
        total_adjustment
    )

    return {
        **team,

        "baseline_rating":
            round(
                baseline,
                2
            ),

        "adjustments": {
            "returning_production":
                round(
                    returning_adjustment,
                    2
                ),

            "roster_snaps":
                round(
                    snap_adjustment,
                    2
                ),

            "incoming_transfer_talent":
                round(
                    incoming_adjustment,
                    2
                ),

            "outgoing_transfer_talent":
                round(
                    outgoing_adjustment,
                    2
                ),

            "recruiting":
                round(
                    recruiting_adjustment,
                    2
                ),

            "total":
                round(
                    total_adjustment,
                    2
                ),
        },

        "preseason_rating":
            round(
                preseason_rating,
                2
            ),
    }


def calculate_preseason_ratings():
    """Build all 2026 preseason ratings."""

    if not check_required_files():
        raise FileNotFoundError(
            "Required 2026 preseason model inputs are missing."
        )

    teams = build_team_records()

    if not teams:
        raise ValueError(
            "No matching teams were available for the 2026 model."
        )

    context = calculate_context(
        teams
    )

    results = []

    for team in teams:

        results.append(
            calculate_team_rating(
                team,
                context
            )
        )

    results.sort(
        key=lambda team:
            team[
                "preseason_rating"
            ],
        reverse=True,
    )

    for rank, team in enumerate(
        results,
        start=1
    ):

        team[
            "preseason_rank"
        ] = rank

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=4
        )

    print("=" * 80)

    print(
        "PROJECT GRIDIRON 2026 PRESEASON POWER RATINGS"
    )

    print("=" * 80)

    print(
        f"Teams rated: "
        f"{len(results)}"
    )

    print()

    print(
        "MODEL"
    )

    print("-" * 80)

    print(
        "Baseline: final 2025 SP+ mapped to "
        "Project Gridiron scale"
    )

    print(
        f"Returning production: "
        f"+/- {RETURNING_MAX_POINTS:.2f} point scale"
    )

    print(
        f"Roster snaps: "
        f"+/- {SNAP_MAX_POINTS:.2f} point experimental scale"
    )

    print(
        f"Incoming 0.90+ transfer: "
        f"+{INCOMING_ELITE_POINTS:.2f} points/player"
    )

    print(
        f"Outgoing 0.90+ transfer: "
        f"-{OUTGOING_ELITE_POINTS:.2f} points/player"
    )

    print(
        "Recruiting: diagnostic only / 0 direct points"
    )

    print()

    print(
        "TOP 25"
    )

    print("-" * 80)

    for team in results[:25]:

        adjustments = team[
            "adjustments"
        ]

        print(
            f"{team['preseason_rank']:>2}. "
            f"{team['team']:<22} "
            f"{team['preseason_rating']:>6.2f} "
            f"(base="
            f"{team['baseline_rating']:.2f}, "
            f"RP="
            f"{adjustments['returning_production']:+.2f}, "
            f"snaps="
            f"{adjustments['roster_snaps']:+.2f}, "
            f"in="
            f"{adjustments['incoming_transfer_talent']:+.2f}, "
            f"out="
            f"{adjustments['outgoing_transfer_talent']:+.2f})"
        )

    print()

    print(
        "BIGGEST POSITIVE ROSTER ADJUSTMENTS"
    )

    print("-" * 80)

    positive = sorted(
        results,
        key=lambda team:
            team[
                "adjustments"
            ][
                "total"
            ],
        reverse=True,
    )

    for team in positive[:15]:

        print(
            f"{team['team']}: "
            f"{team['baseline_rating']:.2f} -> "
            f"{team['preseason_rating']:.2f} "
            f"("
            f"{team['adjustments']['total']:+.2f}"
            f")"
        )

    print()

    print(
        "BIGGEST NEGATIVE ROSTER ADJUSTMENTS"
    )

    print("-" * 80)

    negative = sorted(
        results,
        key=lambda team:
            team[
                "adjustments"
            ][
                "total"
            ],
    )

    for team in negative[:15]:

        print(
            f"{team['team']}: "
            f"{team['baseline_rating']:.2f} -> "
            f"{team['preseason_rating']:.2f} "
            f"("
            f"{team['adjustments']['total']:+.2f}"
            f")"
        )

    print()

    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    calculate_preseason_ratings()
