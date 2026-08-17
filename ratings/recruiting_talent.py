"""
Build team-level recruiting talent metrics for the 2025 recruiting class.

This module measures incoming recruiting talent separately from
transfer portal talent.

Recruiting will eventually receive a relatively small preseason
weight because incoming recruits have little or no proven college
production.

This module does NOT modify the existing power-rating system.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "recruiting_players"
    / "2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "recruiting_talent_2025.json"
)


# Diagnostic thresholds only.
# We will validate them before using them in the model.
BLUE_CHIP_RATING = 0.8900
ELITE_RATING = 0.9500


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


def create_team_profile(team):
    """Create an empty team recruiting profile."""

    return {
        "season": 2025,
        "team": team,

        "total_recruits": 0,

        "rated_recruits": 0,

        "high_school_recruits": 0,

        "juco_recruits": 0,

        "other_recruits": 0,

        "rating_sum": 0.0,

        "average_rating": 0.0,

        "top_10_average_rating": 0.0,

        "top_20_average_rating": 0.0,

        "blue_chip_count": 0,

        "elite_count": 0,

        "five_star_count": 0,

        "four_star_count": 0,

        "three_star_count": 0,

        "two_star_count": 0,

        "positions": {},
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


def classify_recruit_type(
    profile,
    recruit_type
):
    """Track recruit type."""

    recruit_type = (
        recruit_type
        or ""
    ).lower()

    if (
        "highschool"
        in recruit_type
        or
        "high school"
        in recruit_type
    ):

        profile[
            "high_school_recruits"
        ] += 1

    elif (
        "juco"
        in recruit_type
        or
        "junior"
        in recruit_type
    ):

        profile[
            "juco_recruits"
        ] += 1

    else:

        profile[
            "other_recruits"
        ] += 1


def add_recruit(
    profile,
    recruit
):
    """Add one recruit to a team profile."""

    profile[
        "total_recruits"
    ] += 1

    classify_recruit_type(
        profile,
        recruit.get(
            "recruitType"
        )
    )

    position = (
        recruit.get(
            "position"
        )
        or "UNKNOWN"
    )

    profile[
        "positions"
    ][position] = (
        profile[
            "positions"
        ].get(
            position,
            0
        )
        + 1
    )

    stars = recruit.get(
        "stars"
    )

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

    rating = safe_float(
        recruit.get(
            "rating"
        )
    )

    if rating is None:
        return

    profile[
        "rated_recruits"
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


def finalize_team(
    profile,
    team_recruits
):
    """Calculate final recruiting metrics."""

    ratings = []

    for recruit in team_recruits:

        rating = safe_float(
            recruit.get(
                "rating"
            )
        )

        if rating is not None:

            ratings.append(
                rating
            )

    ratings.sort(
        reverse=True
    )

    if ratings:

        profile[
            "average_rating"
        ] = (
            sum(ratings)
            /
            len(ratings)
        )

    top_10 = ratings[:10]

    if top_10:

        profile[
            "top_10_average_rating"
        ] = (
            sum(top_10)
            /
            len(top_10)
        )

    top_20 = ratings[:20]

    if top_20:

        profile[
            "top_20_average_rating"
        ] = (
            sum(top_20)
            /
            len(top_20)
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

    return profile


def calculate_recruiting_talent():
    """Build team-level recruiting talent profiles."""

    recruits = load_json(
        INPUT_FILE
    )

    profiles = {}

    recruits_by_team = {}

    for recruit in recruits:

        team = recruit.get(
            "committedTo"
        )

        if not team:
            continue

        ensure_team(
            profiles,
            team
        )

        recruits_by_team.setdefault(
            team,
            []
        ).append(
            recruit
        )

        add_recruit(
            profiles[
                team
            ],
            recruit
        )

    processed = []

    for (
        team_name,
        profile
    ) in profiles.items():

        processed.append(
            finalize_team(
                profile,
                recruits_by_team[
                    team_name
                ]
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
        "2025 RECRUITING TALENT METRICS"
    )

    print("=" * 60)

    print(
        f"Recruiting records loaded: "
        f"{len(recruits)}"
    )

    print(
        f"Team profiles created: "
        f"{len(processed)}"
    )

    print()

    print(
        "TOP 15 BY TOP-10 AVERAGE RATING"
    )

    print("-" * 60)

    top_teams = sorted(
        processed,
        key=lambda team:
            team[
                "top_10_average_rating"
            ],
        reverse=True,
    )

    for team in top_teams[:15]:

        print(
            f"{team['team']}: "
            f"top10="
            f"{team['top_10_average_rating']:.4f}, "
            f"avg="
            f"{team['average_rating']:.4f}, "
            f"blue_chips="
            f"{team['blue_chip_count']}, "
            f"elite="
            f"{team['elite_count']}, "
            f"5-star="
            f"{team['five_star_count']}, "
            f"4-star="
            f"{team['four_star_count']}"
        )

    print()

    print(
        "TOP 15 BY BLUE-CHIP COUNT"
    )

    print("-" * 60)

    blue_chip_teams = sorted(
        processed,
        key=lambda team:
            (
                team[
                    "blue_chip_count"
                ],
                team[
                    "top_10_average_rating"
                ]
            ),
        reverse=True,
    )

    for team in blue_chip_teams[:15]:

        print(
            f"{team['team']}: "
            f"blue_chips="
            f"{team['blue_chip_count']}, "
            f"elite="
            f"{team['elite_count']}, "
            f"top10="
            f"{team['top_10_average_rating']:.4f}, "
            f"recruits="
            f"{team['total_recruits']}"
        )

    print()

    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    calculate_recruiting_talent()
