"""
Process CFBD transfer portal data into team-level profiles.

The processor separates incoming and outgoing transfers and
summarizes available transfer talent by team and position.

CFBD transfer ratings/stars may be null, so missing values
are handled safely.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "transfer_portal"
    / "2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "transfer_portal_2025.json"
)


POSITIONS = [
    "QB",
    "RB",
    "FB",
    "WR",
    "TE",
    "OL",
    "OT",
    "OG",
    "C",
    "DL",
    "DT",
    "DE",
    "EDGE",
    "LB",
    "CB",
    "S",
    "DB",
    "K",
    "P",
    "LS",
]


def load_records():
    """Load raw transfer portal records."""

    with INPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def create_team_profile(team):
    """Create an empty team transfer profile."""

    return {
        "season": 2025,
        "team": team,

        "incoming": {
            "count": 0,
            "rated_count": 0,
            "average_rating": 0,
            "total_rating": 0,
            "stars_count": 0,
            "total_stars": 0,
            "positions": {},
        },

        "outgoing": {
            "count": 0,
            "rated_count": 0,
            "average_rating": 0,
            "total_rating": 0,
            "stars_count": 0,
            "total_stars": 0,
            "positions": {},
        },

        "net": {
            "transfer_count": 0,
            "rated_count_difference": 0,
            "rating_difference": 0,
            "star_difference": 0,
        },
    }


def ensure_team(
    profiles,
    team
):
    """Create a team profile if it does not exist."""

    if not team:
        return

    if team not in profiles:
        profiles[team] = create_team_profile(team)


def add_transfer(
    profile,
    transfer
):
    """Add one transfer to a team profile."""

    position = transfer.get(
        "position"
    )

    if not position:
        position = "UNKNOWN"

    profile["count"] += 1

    position_counts = profile[
        "positions"
    ]

    position_counts[position] = (
        position_counts.get(
            position,
            0
        )
        + 1
    )

    rating = transfer.get(
        "rating"
    )

    if rating is not None:
        try:
            rating = float(rating)

            profile[
                "rated_count"
            ] += 1

            profile[
                "total_rating"
            ] += rating

        except (
            TypeError,
            ValueError
        ):
            pass

    stars = transfer.get(
        "stars"
    )

    if stars is not None:
        try:
            stars = float(stars)

            profile[
                "stars_count"
            ] += 1

            profile[
                "total_stars"
            ] += stars

        except (
            TypeError,
            ValueError
        ):
            pass


def finalize_profile(profile):
    """Calculate averages and net transfer metrics."""

    incoming = profile[
        "incoming"
    ]

    outgoing = profile[
        "outgoing"
    ]

    if incoming[
        "rated_count"
    ] > 0:

        incoming[
            "average_rating"
        ] = (
            incoming[
                "total_rating"
            ]
            /
            incoming[
                "rated_count"
            ]
        )

    if outgoing[
        "rated_count"
    ] > 0:

        outgoing[
            "average_rating"
        ] = (
            outgoing[
                "total_rating"
            ]
            /
            outgoing[
                "rated_count"
            ]
        )

    profile[
        "net"
    ] = {
        "transfer_count":
            incoming["count"]
            -
            outgoing["count"],

        "rated_count_difference":
            incoming["rated_count"]
            -
            outgoing["rated_count"],

        "rating_difference":
            incoming["total_rating"]
            -
            outgoing["total_rating"],

        "star_difference":
            incoming["total_stars"]
            -
            outgoing["total_stars"],
    }

    incoming[
        "average_rating"
    ] = round(
        incoming[
            "average_rating"
        ],
        4
    )

    outgoing[
        "average_rating"
    ] = round(
        outgoing[
            "average_rating"
        ],
        4
    )

    incoming[
        "total_rating"
    ] = round(
        incoming[
            "total_rating"
        ],
        4
    )

    outgoing[
        "total_rating"
    ] = round(
        outgoing[
            "total_rating"
        ],
        4
    )

    incoming[
        "total_stars"
    ] = round(
        incoming[
            "total_stars"
        ],
        4
    )

    outgoing[
        "total_stars"
    ] = round(
        outgoing[
            "total_stars"
        ],
        4
    )

    profile[
        "net"
    ][
        "rating_difference"
    ] = round(
        profile[
            "net"
        ][
            "rating_difference"
        ],
        4
    )

    profile[
        "net"
    ][
        "star_difference"
    ] = round(
        profile[
            "net"
        ][
            "star_difference"
        ],
        4
    )

    return profile


def process_transfer_portal():
    """Process all transfer portal records."""

    records = load_records()

    profiles = {}

    for transfer in records:

        origin = transfer.get(
            "origin"
        )

        destination = transfer.get(
            "destination"
        )

        # Create profiles for both sides
        # when a team is available.
        ensure_team(
            profiles,
            origin
        )

        ensure_team(
            profiles,
            destination
        )

        # Outgoing transfer.
        if origin:

            add_transfer(
                profiles[
                    origin
                ][
                    "outgoing"
                ],
                transfer
            )

        # Incoming transfer.
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

    for team in profiles.values():

        processed.append(
            finalize_profile(
                team
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

    incoming_total = sum(
        team[
            "incoming"
        ][
            "count"
        ]
        for team in processed
    )

    outgoing_total = sum(
        team[
            "outgoing"
        ][
            "count"
        ]
        for team in processed
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
        f"{incoming_total}"
    )

    print(
        f"Outgoing transfers: "
        f"{outgoing_total}"
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
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    process_transfer_portal()
