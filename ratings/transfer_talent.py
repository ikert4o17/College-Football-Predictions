"""
Build team-level transfer talent metrics from the enriched
2025 transfer portal dataset.

The goal is to measure transfer QUALITY, not just transfer volume.

Portal-time ratings are preferred.
Original recruiting ratings are used only as a fallback.

This module does NOT modify the existing power-rating system.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "enriched_transfer_portal_2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "transfer_talent_2025.json"
)


# This is only a descriptive threshold for diagnostics.
# It is NOT yet a model weight or replacement-level cutoff.
HIGH_END_RATING = 0.9000


def load_json(path):
    """Load JSON data."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def safe_float(value):
    """Convert a value safely to float."""

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return None


def create_side_profile():
    """Create an empty incoming/outgoing transfer profile."""

    return {
        "count": 0,

        "rated_count": 0,

        "portal_rated_count": 0,

        "recruiting_fallback_count": 0,

        "unrated_count": 0,

        "rating_sum": 0.0,

        "average_rating": 0.0,

        "high_end_count": 0,

        "positions": {},
    }


def create_team_profile(team):
    """Create an empty team transfer talent profile."""

    return {
        "season": 2025,

        "team": team,

        "incoming": create_side_profile(),

        "outgoing": create_side_profile(),

        "net": {
            "transfer_count": 0,

            "rated_count": 0,

            "rating_sum": 0.0,

            "average_rating_difference": 0.0,

            "high_end_count": 0,
        },
    }


def ensure_team(
    profiles,
    team
):
    """Create a team profile if needed."""

    if not team:
        return

    if team not in profiles:
        profiles[team] = (
            create_team_profile(
                team
            )
        )


def add_transfer(
    side,
    transfer
):
    """Add one transfer to an incoming/outgoing profile."""

    side["count"] += 1

    position = (
        transfer.get(
            "position"
        )
        or "UNKNOWN"
    )

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

    talent = transfer.get(
        "talent",
        {}
    )

    rating = safe_float(
        talent.get(
            "effective_rating"
        )
    )

    source = talent.get(
        "effective_rating_source",
        "unrated"
    )

    if rating is None:

        side[
            "unrated_count"
        ] += 1

        return

    side[
        "rated_count"
    ] += 1

    side[
        "rating_sum"
    ] += rating

    if source == "portal":

        side[
            "portal_rated_count"
        ] += 1

    elif (
        source
        == "recruiting_fallback"
    ):

        side[
            "recruiting_fallback_count"
        ] += 1

    if rating >= HIGH_END_RATING:

        side[
            "high_end_count"
        ] += 1


def finalize_side(side):
    """Calculate side-level averages."""

    rated_count = side[
        "rated_count"
    ]

    if rated_count > 0:

        side[
            "average_rating"
        ] = (
            side[
                "rating_sum"
            ]
            /
            rated_count
        )

    side[
        "rating_sum"
    ] = round(
        side[
            "rating_sum"
        ],
        4
    )

    side[
        "average_rating"
    ] = round(
        side[
            "average_rating"
        ],
        4
    )

    return side


def finalize_team(profile):
    """Calculate team-level net transfer metrics."""

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
        "transfer_count":
            incoming["count"]
            -
            outgoing["count"],

        "rated_count":
            incoming[
                "rated_count"
            ]
            -
            outgoing[
                "rated_count"
            ],

        "rating_sum":
            round(
                incoming[
                    "rating_sum"
                ]
                -
                outgoing[
                    "rating_sum"
                ],
                4
            ),

        "average_rating_difference":
            round(
                incoming[
                    "average_rating"
                ]
                -
                outgoing[
                    "average_rating"
                ],
                4
            ),

        "high_end_count":
            incoming[
                "high_end_count"
            ]
            -
            outgoing[
                "high_end_count"
            ],
    }

    return profile


def calculate_transfer_talent():
    """Build team-level transfer talent metrics."""

    records = load_json(
        INPUT_FILE
    )

    profiles = {}

    for transfer in records:

        origin = transfer.get(
            "origin"
        )

        destination = transfer.get(
            "destination"
        )

        ensure_team(
            profiles,
            origin
        )

        ensure_team(
            profiles,
            destination
        )

        if origin:

            add_transfer(
                profiles[
                    origin
                ][
                    "outgoing"
                ],
                transfer
            )

        if destination:

            add_transfer(
                profiles[
                    destination
                ][
                    "incoming"
                ],
                transfer
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
            team["team"]
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            processed,
            file,
            indent=4
        )

    print("=" * 60)

    print(
        "TEAM TRANSFER TALENT METRICS"
    )

    print("=" * 60)

    print(
        f"Team profiles created: "
        f"{len(processed)}"
    )

    total_incoming = sum(
        team[
            "incoming"
        ][
            "count"
        ]
        for team in processed
    )

    total_outgoing = sum(
        team[
            "outgoing"
        ][
            "count"
        ]
        for team in processed
    )

    incoming_rated = sum(
        team[
            "incoming"
        ][
            "rated_count"
        ]
        for team in processed
    )

    outgoing_rated = sum(
        team[
            "outgoing"
        ][
            "rated_count"
        ]
        for team in processed
    )

    print(
        f"Incoming transfers: "
        f"{total_incoming}"
    )

    print(
        f"Incoming rated transfers: "
        f"{incoming_rated}"
    )

    print(
        f"Outgoing transfers: "
        f"{total_outgoing}"
    )

    print(
        f"Outgoing rated transfers: "
        f"{outgoing_rated}"
    )

    print()

    print(
        "TOP 15 TEAMS BY NET RATING SUM"
    )

    print("-" * 60)

    top_teams = sorted(
        processed,
        key=lambda team:
            team[
                "net"
            ][
                "rating_sum"
            ],
        reverse=True,
    )

    for team in top_teams[:15]:

        print(
            f"{team['team']}: "
            f"net_rating="
            f"{team['net']['rating_sum']:+.4f}, "
            f"in="
            f"{team['incoming']['count']}, "
            f"out="
            f"{team['outgoing']['count']}, "
            f"in_avg="
            f"{team['incoming']['average_rating']:.4f}, "
            f"out_avg="
            f"{team['outgoing']['average_rating']:.4f}, "
            f"high_end_net="
            f"{team['net']['high_end_count']:+d}"
        )

    print()

    print(
        "BOTTOM 15 TEAMS BY NET RATING SUM"
    )

    print("-" * 60)

    bottom_teams = sorted(
        processed,
        key=lambda team:
            team[
                "net"
            ][
                "rating_sum"
            ],
    )

    for team in bottom_teams[:15]:

        print(
            f"{team['team']}: "
            f"net_rating="
            f"{team['net']['rating_sum']:+.4f}, "
            f"in="
            f"{team['incoming']['count']}, "
            f"out="
            f"{team['outgoing']['count']}, "
            f"in_avg="
            f"{team['incoming']['average_rating']:.4f}, "
            f"out_avg="
            f"{team['outgoing']['average_rating']:.4f}, "
            f"high_end_net="
            f"{team['net']['high_end_count']:+d}"
        )

    print()

    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    calculate_transfer_talent()
