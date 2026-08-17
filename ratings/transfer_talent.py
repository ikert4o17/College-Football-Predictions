"""
Build team-level transfer talent metrics from enriched
transfer portal datasets.

Usage:
    python -m ratings.transfer_talent 2025
    python -m ratings.transfer_talent 2026

Input:
    data/processed/enriched_transfer_portal_<year>.json

Output:
    data/processed/transfer_talent_<year>.json

The goal is to measure transfer QUALITY, not just transfer volume.

Portal-time ratings are preferred.
Original recruiting ratings are used only as a fallback.

This module does NOT modify the existing power-rating system.
"""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


HIGH_END_RATING = 0.9000


def input_file(year):
    """Return enriched transfer portal input path."""

    return (
        PROJECT_ROOT
        / "data"
        / "processed"
        / f"enriched_transfer_portal_{year}.json"
    )


def output_file(year):
    """Return team-level transfer talent output path."""

    return (
        PROJECT_ROOT
        / "data"
        / "processed"
        / f"transfer_talent_{year}.json"
    )


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


def create_team_profile(
    team,
    season
):
    """Create an empty team transfer talent profile."""

    return {
        "season": season,

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
    team,
    season
):
    """Create a team profile if needed."""

    if not team:
        return

    if team not in profiles:

        profiles[
            team
        ] = create_team_profile(
            team,
            season
        )


def add_transfer(
    side,
    transfer
):
    """Add one transfer to an incoming/outgoing profile."""

    side[
        "count"
    ] += 1

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
        ==
        "recruiting_fallback"
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
            incoming[
                "count"
            ]
            -
            outgoing[
                "count"
            ],

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


def calculate_transfer_talent(year):
    """Build team-level transfer talent metrics for one season."""

    source = input_file(
        year
    )

    destination = output_file(
        year
    )

    if not source.exists():

        raise FileNotFoundError(
            f"Enriched transfer portal input not found: "
            f"{source}"
        )

    records = load_json(
        source
    )

    profiles = {}

    for transfer in records:

        origin = transfer.get(
            "origin"
        )

        destination_team = transfer.get(
            "destination"
        )

        ensure_team(
            profiles,
            origin,
            year
        )

        ensure_team(
            profiles,
            destination_team,
            year
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

        if destination_team:

            add_transfer(
                profiles[
                    destination_team
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
            team[
                "team"
            ]
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

    print("=" * 70)

    print(
        f"{year} TEAM TRANSFER TALENT METRICS"
    )

    print("=" * 70)

    print(
        f"Transfer records loaded: "
        f"{len(records)}"
    )

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

    incoming_high_end = sum(
        team[
            "incoming"
        ][
            "high_end_count"
        ]
        for team in processed
    )

    outgoing_high_end = sum(
        team[
            "outgoing"
        ][
            "high_end_count"
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
        f"Incoming 0.90+ transfers: "
        f"{incoming_high_end}"
    )

    print(
        f"Outgoing transfers: "
        f"{total_outgoing}"
    )

    print(
        f"Outgoing rated transfers: "
        f"{outgoing_rated}"
    )

    print(
        f"Outgoing 0.90+ transfers: "
        f"{outgoing_high_end}"
    )

    print()

    print(
        "TOP 15 TEAMS BY INCOMING 0.90+ TRANSFERS"
    )

    print("-" * 70)

    incoming_elite = sorted(
        processed,
        key=lambda team:
            (
                team[
                    "incoming"
                ][
                    "high_end_count"
                ],
                team[
                    "incoming"
                ][
                    "average_rating"
                ],
            ),
        reverse=True,
    )

    for team in incoming_elite[:15]:

        print(
            f"{team['team']}: "
            f"high_end="
            f"{team['incoming']['high_end_count']}, "
            f"in="
            f"{team['incoming']['count']}, "
            f"avg="
            f"{team['incoming']['average_rating']:.4f}"
        )

    print()

    print(
        "TOP 15 TEAMS BY OUTGOING 0.90+ TRANSFERS"
    )

    print("-" * 70)

    outgoing_elite = sorted(
        processed,
        key=lambda team:
            (
                team[
                    "outgoing"
                ][
                    "high_end_count"
                ],
                team[
                    "outgoing"
                ][
                    "average_rating"
                ],
            ),
        reverse=True,
    )

    for team in outgoing_elite[:15]:

        print(
            f"{team['team']}: "
            f"high_end="
            f"{team['outgoing']['high_end_count']}, "
            f"out="
            f"{team['outgoing']['count']}, "
            f"avg="
            f"{team['outgoing']['average_rating']:.4f}"
        )

    print()

    print(
        "TOP 15 TEAMS BY NET HIGH-END TRANSFERS"
    )

    print("-" * 70)

    net_elite = sorted(
        processed,
        key=lambda team:
            team[
                "net"
            ][
                "high_end_count"
            ],
        reverse=True,
    )

    for team in net_elite[:15]:

        print(
            f"{team['team']}: "
            f"net_high_end="
            f"{team['net']['high_end_count']:+d}, "
            f"in_high_end="
            f"{team['incoming']['high_end_count']}, "
            f"out_high_end="
            f"{team['outgoing']['high_end_count']}"
        )

    print()

    print(
        "BOTTOM 15 TEAMS BY NET HIGH-END TRANSFERS"
    )

    print("-" * 70)

    bottom_elite = sorted(
        processed,
        key=lambda team:
            team[
                "net"
            ][
                "high_end_count"
            ]
    )

    for team in bottom_elite[:15]:

        print(
            f"{team['team']}: "
            f"net_high_end="
            f"{team['net']['high_end_count']:+d}, "
            f"in_high_end="
            f"{team['incoming']['high_end_count']}, "
            f"out_high_end="
            f"{team['outgoing']['high_end_count']}"
        )

    print()

    print(
        f"Saved to {destination}"
    )


if __name__ == "__main__":

    year = 2025

    if len(sys.argv) > 1:

        year = int(
            sys.argv[1]
        )

    calculate_transfer_talent(
        year
    )
