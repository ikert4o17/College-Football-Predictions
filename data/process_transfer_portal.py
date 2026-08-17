"""
Process CFBD transfer portal data into team-level profiles.

Usage:
    python -m data.process_transfer_portal 2025
    python -m data.process_transfer_portal 2026

The raw input is expected at:
    data/raw/transfer_portal/<year>.json

The processed output is written to:
    data/processed/transfer_portal_<year>.json
"""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def input_file(year):
    """Return raw transfer portal input path."""

    return (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "transfer_portal"
        / f"{year}.json"
    )


def output_file(year):
    """Return processed transfer portal output path."""

    return (
        PROJECT_ROOT
        / "data"
        / "processed"
        / f"transfer_portal_{year}.json"
    )


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


def safe_int(value):
    """Safely convert a value to int."""

    if value is None:
        return None

    try:
        return int(value)

    except (
        TypeError,
        ValueError
    ):
        return None


def create_team_profile(team, season):
    """Create an empty team transfer profile."""

    return {
        "season": season,
        "team": team,

        "incoming": {
            "count": 0,
            "rated_count": 0,
            "rating_sum": 0.0,
            "stars_sum": 0,
            "average_rating": 0.0,
            "average_stars": 0.0,
            "players": [],
        },

        "outgoing": {
            "count": 0,
            "rated_count": 0,
            "rating_sum": 0.0,
            "stars_sum": 0,
            "average_rating": 0.0,
            "average_stars": 0.0,
            "players": [],
        },
    }


def ensure_team(
    profiles,
    team,
    season
):
    """Create team profile if needed."""

    if not team:
        return

    if team not in profiles:
        profiles[team] = (
            create_team_profile(
                team,
                season
            )
        )


def player_name(record):
    """Build transfer player's full name."""

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


def add_transfer(
    side,
    record
):
    """Add one transfer record to a side profile."""

    side[
        "count"
    ] += 1

    rating = safe_float(
        record.get(
            "rating"
        )
    )

    stars = safe_int(
        record.get(
            "stars"
        )
    )

    if rating is not None:

        side[
            "rated_count"
        ] += 1

        side[
            "rating_sum"
        ] += rating

    if stars is not None:

        side[
            "stars_sum"
        ] += stars

    side[
        "players"
    ].append(
        {
            "player":
                player_name(
                    record
                ),

            "position":
                record.get(
                    "position"
                ),

            "origin":
                record.get(
                    "origin"
                ),

            "destination":
                record.get(
                    "destination"
                ),

            "transfer_date":
                record.get(
                    "transferDate"
                ),

            "rating":
                rating,

            "stars":
                stars,

            "eligibility":
                record.get(
                    "eligibility"
                ),
        }
    )


def finalize_side(side):
    """Calculate averages for one side."""

    if (
        side[
            "rated_count"
        ] > 0
    ):

        side[
            "average_rating"
        ] = (
            side[
                "rating_sum"
            ]
            /
            side[
                "rated_count"
            ]
        )

    starred_players = [
        player
        for player in side[
            "players"
        ]
        if player[
            "stars"
        ] is not None
    ]

    if starred_players:

        side[
            "average_stars"
        ] = (
            sum(
                player[
                    "stars"
                ]
                for player in starred_players
            )
            /
            len(
                starred_players
            )
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

    side[
        "average_stars"
    ] = round(
        side[
            "average_stars"
        ],
        3
    )

    return side


def finalize_team(profile):
    """Finalize one team profile."""

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
        "count":
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

        "stars_sum":
            incoming[
                "stars_sum"
            ]
            -
            outgoing[
                "stars_sum"
            ],
    }

    return profile


def process_transfer_portal(year):
    """Process one season of transfer portal data."""

    source = input_file(
        year
    )

    destination = output_file(
        year
    )

    if not source.exists():

        raise FileNotFoundError(
            f"Transfer portal input file not found: "
            f"{source}"
        )

    with source.open(
        "r",
        encoding="utf-8"
    ) as file:

        records = json.load(
            file
        )

    profiles = {}

    total_incoming = 0
    total_outgoing = 0

    for record in records:

        origin = record.get(
            "origin"
        )

        destination_team = (
            record.get(
                "destination"
            )
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
                record
            )

            total_outgoing += 1

        if destination_team:

            add_transfer(
                profiles[
                    destination_team
                ][
                    "incoming"
                ],
                record
            )

            total_incoming += 1

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

    teams_with_incoming = sum(
        1
        for team in processed
        if team[
            "incoming"
        ][
            "count"
        ] > 0
    )

    teams_with_outgoing = sum(
        1
        for team in processed
        if team[
            "outgoing"
        ][
            "count"
        ] > 0
    )

    print("=" * 70)

    print(
        f"{year} TRANSFER PORTAL PROCESSING"
    )

    print("=" * 70)

    print(
        f"Processed "
        f"{len(records)} "
        f"transfer portal records."
    )

    print(
        f"Team profiles created: "
        f"{len(processed)}"
    )

    print(
        f"Incoming transfers: "
        f"{total_incoming}"
    )

    print(
        f"Outgoing transfers: "
        f"{total_outgoing}"
    )

    print(
        f"Teams with incoming transfers: "
        f"{teams_with_incoming}"
    )

    print(
        f"Teams with outgoing transfers: "
        f"{teams_with_outgoing}"
    )

    print(
        f"Saved to {destination}"
    )


if __name__ == "__main__":

    year = 2025

    if len(sys.argv) > 1:

        year = int(
            sys.argv[1]
        )

    process_transfer_portal(
        year
    )
