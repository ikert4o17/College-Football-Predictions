"""
Calculate an initial 2025 FBS power rating.

This is the first baseline rating system.
It is intentionally transparent and will be
validated and improved against historical results.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

STRENGTH_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "team_strength_2025.json"
)

RESULTS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "team_results_2025.json"
)

SOS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "strength_of_schedule_2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "power_ratings_2025.json"
)


def load_json(path):
    """Load a JSON file."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def normalize(value, minimum, maximum):
    """Normalize a value to a 0-100 scale."""

    if maximum == minimum:
        return 50.0

    return (
        (value - minimum)
        / (maximum - minimum)
        * 100
    )


def build_lookup(records):
    """Create a team lookup."""

    return {
        record["team"]: record
        for record in records
    }


def calculate_power_ratings():
    """Calculate initial power ratings."""

    strength_records = load_json(
        STRENGTH_FILE
    )

    result_records = load_json(
        RESULTS_FILE
    )

    sos_records = load_json(
        SOS_FILE
    )

    strength_lookup = build_lookup(
        strength_records
    )

    result_lookup = build_lookup(
        result_records
    )

    sos_lookup = build_lookup(
        sos_records
    )

    teams = []

    for team_name, strength in strength_lookup.items():

        if team_name not in result_lookup:
            continue

        if team_name not in sos_lookup:
            continue

        results = result_lookup[
            team_name
        ]

        sos = sos_lookup[
            team_name
        ]

        offense = strength["offense"]
        defense = strength["defense"]

        teams.append(
            {
                "team": team_name,

                "total_yards_per_game":
                    offense[
                        "total_yards_per_game"
                    ],

                "rushing_yards_per_game":
                    offense[
                        "rushing_yards_per_game"
                    ],

                "passing_yards_per_game":
                    offense[
                        "passing_yards_per_game"
                    ],

                "yards_per_rush":
                    offense[
                        "yards_per_rush"
                    ],

                "net_yards_per_pass":
                    offense[
                        "net_yards_per_pass"
                    ],

                "third_down_conversion":
                    offense[
                        "third_down_conversion"
                    ],

                "total_yards_allowed_per_game":
                    defense[
                        "total_yards_allowed_per_game"
                    ],

                "rushing_yards_allowed_per_game":
                    defense[
                        "rushing_yards_allowed_per_game"
                    ],

                "passing_yards_allowed_per_game":
                    defense[
                        "passing_yards_allowed_per_game"
                    ],

                "third_down_defense":
                    defense[
                        "third_down_defense"
                    ],

                "sacks_per_game":
                    defense[
                        "sacks_per_game"
                    ],

                "point_margin_per_game":
                    results[
                        "point_margin_per_game"
                    ],

                "win_percentage":
                    results[
                        "win_percentage"
                    ],

                "sos":
                    sos[
                        "average_opponent_margin"
                    ],
            }
        )

    # Determine league-wide ranges.
    metrics = [
        "total_yards_per_game",
        "rushing_yards_per_game",
        "passing_yards_per_game",
        "yards_per_rush",
        "net_yards_per_pass",
        "third_down_conversion",
        "total_yards_allowed_per_game",
        "rushing_yards_allowed_per_game",
        "passing_yards_allowed_per_game",
        "third_down_defense",
        "sacks_per_game",
        "point_margin_per_game",
        "win_percentage",
        "sos",
    ]

    ranges = {}

    for metric in metrics:

        values = [
            team[metric]
            for team in teams
        ]

        ranges[metric] = (
            min(values),
            max(values),
        )

    ratings = []

    for team in teams:

        # Offensive components.
        offense_score = (
            normalize(
                team["total_yards_per_game"],
                *ranges[
                    "total_yards_per_game"
                ],
            )
            * 0.20
            +
            normalize(
                team["rushing_yards_per_game"],
                *ranges[
                    "rushing_yards_per_game"
                ],
            )
            * 0.15
            +
            normalize(
                team["passing_yards_per_game"],
                *ranges[
                    "passing_yards_per_game"
                ],
            )
            * 0.15
            +
            normalize(
                team["yards_per_rush"],
                *ranges[
                    "yards_per_rush"
                ],
            )
            * 0.15
            +
            normalize(
                team["net_yards_per_pass"],
                *ranges[
                    "net_yards_per_pass"
                ],
            )
            * 0.20
            +
            normalize(
                team["third_down_conversion"],
                *ranges[
                    "third_down_conversion"
                ],
            )
            * 0.15
        )

        # Defensive components.
        # Lower yards allowed is better.
        defense_score = (
            normalize(
                ranges[
                    "total_yards_allowed_per_game"
                ][1]
                - team[
                    "total_yards_allowed_per_game"
                ],
                0,
                ranges[
                    "total_yards_allowed_per_game"
                ][1]
                - ranges[
                    "total_yards_allowed_per_game"
                ][0],
            )
            * 0.30
            +
            normalize(
                ranges[
                    "rushing_yards_allowed_per_game"
                ][1]
                - team[
                    "rushing_yards_allowed_per_game"
                ],
                0,
                ranges[
                    "rushing_yards_allowed_per_game"
                ][1]
                - ranges[
                    "rushing_yards_allowed_per_game"
                ][0],
            )
            * 0.20
            +
            normalize(
                ranges[
                    "passing_yards_allowed_per_game"
                ][1]
                - team[
                    "passing_yards_allowed_per_game"
                ],
                0,
                ranges[
                    "passing_yards_allowed_per_game"
                ][1]
                - ranges[
                    "passing_yards_allowed_per_game"
                ][0],
            )
            * 0.20
            +
            normalize(
                1
                - team[
                    "third_down_defense"
                ],
                0,
                1,
            )
            * 0.15
            +
            normalize(
                team["sacks_per_game"],
                *ranges[
                    "sacks_per_game"
                ],
            )
            * 0.15
        )

        # Results component.
        results_score = (
            normalize(
                team["point_margin_per_game"],
                *ranges[
                    "point_margin_per_game"
                ],
            )
            * 0.75
            +
            normalize(
                team["win_percentage"],
                *ranges[
                    "win_percentage"
                ],
            )
            * 0.25
        )

        # Schedule component.
        sos_score = normalize(
            team["sos"],
            *ranges["sos"],
        )

        # Initial overall rating.
        rating = (
            offense_score * 0.30
            +
            defense_score * 0.30
            +
            results_score * 0.30
            +
            sos_score * 0.10
        )

        ratings.append(
            {
                "season": 2025,
                "team": team["team"],
                "offense_score":
                    round(offense_score, 2),
                "defense_score":
                    round(defense_score, 2),
                "results_score":
                    round(results_score, 2),
                "sos_score":
                    round(sos_score, 2),
                "power_rating":
                    round(rating, 2),
            }
        )

    ratings.sort(
        key=lambda team:
            team["power_rating"],
        reverse=True,
    )

    for index, team in enumerate(
        ratings,
        start=1
    ):
        team["rank"] = index

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            ratings,
            file,
            indent=4
        )

    print(
        f"Calculated power ratings for "
        f"{len(ratings)} teams."
    )

    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    calculate_power_ratings()
