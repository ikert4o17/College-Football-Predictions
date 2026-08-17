"""
Build team-level NFL Draft loss metrics for the 2025 draft.

The 2025 NFL Draft represents talent lost after the 2024
college football season and before the 2025 season.

This module creates several draft-loss signals:

- Total drafted players
- First-round picks
- Day 1 / Day 2 / Day 3 losses
- Top-50 and Top-100 picks
- Pre-draft grade totals
- Pre-draft grade averages
- Draft capital
- Quarterback losses

This module does NOT modify the production power-rating system.
"""

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "draft_picks"
    / "2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "draft_losses_2025.json"
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


def safe_int(value):
    """Convert a value safely to int."""

    if value is None:
        return None

    try:
        return int(value)

    except (
        TypeError,
        ValueError
    ):
        return None


def calculate_draft_capital(overall_pick):
    """
    Convert overall pick number into a simple draft-capital value.

    Earlier picks receive substantially more value than later picks.

    This is a diagnostic transformation only.
    We will validate whether it is useful before applying it
    to the preseason model.
    """

    if overall_pick is None:
        return 0.0

    if overall_pick <= 0:
        return 0.0

    return (
        100.0
        /
        math.sqrt(
            overall_pick
        )
    )


def create_team_profile(team):
    """Create an empty team draft-loss profile."""

    return {
        "season": 2025,

        "team": team,

        "drafted_count": 0,

        "round_1_count": 0,

        "round_2_count": 0,

        "round_3_count": 0,

        "round_4_count": 0,

        "round_5_count": 0,

        "round_6_count": 0,

        "round_7_count": 0,

        "day_1_count": 0,

        "day_2_count": 0,

        "day_3_count": 0,

        "top_10_count": 0,

        "top_25_count": 0,

        "top_50_count": 0,

        "top_100_count": 0,

        "pre_draft_grade_sum": 0.0,

        "pre_draft_grade_average": 0.0,

        "draft_capital": 0.0,

        "qb_drafted_count": 0,

        "qb_round_1_count": 0,

        "positions": {},

        "players": [],
    }


def ensure_team(
    profiles,
    team
):
    """Create a team profile if needed."""

    if not team:
        return

    if team not in profiles:

        profiles[
            team
        ] = create_team_profile(
            team
        )


def normalize_position(position):
    """Normalize draft position labels."""

    if not position:
        return "UNKNOWN"

    position = (
        str(position)
        .strip()
        .upper()
    )

    aliases = {
        "QUARTERBACK": "QB",
        "RUNNING BACK": "RB",
        "WIDE RECEIVER": "WR",
        "TIGHT END": "TE",
        "OFFENSIVE TACKLE": "OT",
        "OFFENSIVE GUARD": "OG",
        "CENTER": "C",
        "DEFENSIVE END": "DE",
        "DEFENSIVE TACKLE": "DT",
        "LINEBACKER": "LB",
        "CORNERBACK": "CB",
        "SAFETY": "S",
        "KICKER": "K",
        "PUNTER": "P",
    }

    return aliases.get(
        position,
        position
    )


def add_pick(
    profile,
    pick
):
    """Add one NFL Draft pick to a team profile."""

    profile[
        "drafted_count"
    ] += 1

    round_number = safe_int(
        pick.get(
            "round"
        )
    )

    overall_pick = safe_int(
        pick.get(
            "overall"
        )
    )

    grade = safe_float(
        pick.get(
            "preDraftGrade"
        )
    )

    position = normalize_position(
        pick.get(
            "position"
        )
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

    if (
        round_number is not None
        and 1 <= round_number <= 7
    ):

        profile[
            f"round_{round_number}_count"
        ] += 1

    if round_number == 1:

        profile[
            "day_1_count"
        ] += 1

    elif (
        round_number is not None
        and round_number in {
            2,
            3,
        }
    ):

        profile[
            "day_2_count"
        ] += 1

    elif (
        round_number is not None
        and round_number >= 4
    ):

        profile[
            "day_3_count"
        ] += 1

    if overall_pick is not None:

        if overall_pick <= 10:

            profile[
                "top_10_count"
            ] += 1

        if overall_pick <= 25:

            profile[
                "top_25_count"
            ] += 1

        if overall_pick <= 50:

            profile[
                "top_50_count"
            ] += 1

        if overall_pick <= 100:

            profile[
                "top_100_count"
            ] += 1

        profile[
            "draft_capital"
        ] += (
            calculate_draft_capital(
                overall_pick
            )
        )

    if grade is not None:

        profile[
            "pre_draft_grade_sum"
        ] += grade

    if position == "QB":

        profile[
            "qb_drafted_count"
        ] += 1

        if round_number == 1:

            profile[
                "qb_round_1_count"
            ] += 1

    profile[
        "players"
    ].append(
        {
            "name":
                pick.get(
                    "name"
                ),

            "collegeAthleteId":
                pick.get(
                    "collegeAthleteId"
                ),

            "position":
                position,

            "round":
                round_number,

            "overall":
                overall_pick,

            "preDraftGrade":
                grade,

            "preDraftRanking":
                pick.get(
                    "preDraftRanking"
                ),

            "preDraftPositionRanking":
                pick.get(
                    "preDraftPositionRanking"
                ),

            "nflTeam":
                pick.get(
                    "nflTeam"
                ),
        }
    )


def finalize_team(profile):
    """Calculate final team draft-loss metrics."""

    graded_players = [
        player
        for player in profile[
            "players"
        ]
        if player[
            "preDraftGrade"
        ] is not None
    ]

    if graded_players:

        profile[
            "pre_draft_grade_average"
        ] = (
            profile[
                "pre_draft_grade_sum"
            ]
            /
            len(
                graded_players
            )
        )

    profile[
        "pre_draft_grade_sum"
    ] = round(
        profile[
            "pre_draft_grade_sum"
        ],
        2
    )

    profile[
        "pre_draft_grade_average"
    ] = round(
        profile[
            "pre_draft_grade_average"
        ],
        2
    )

    profile[
        "draft_capital"
    ] = round(
        profile[
            "draft_capital"
        ],
        4
    )

    return profile


def calculate_draft_losses():
    """Build team-level NFL Draft loss profiles."""

    picks = load_json(
        INPUT_FILE
    )

    profiles = {}

    for pick in picks:

        team = pick.get(
            "collegeTeam"
        )

        if not team:
            continue

        ensure_team(
            profiles,
            team
        )

        add_pick(
            profiles[
                team
            ],
            pick
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

    print("=" * 70)

    print(
        "2025 NFL DRAFT LOSS METRICS"
    )

    print("=" * 70)

    print(
        f"Draft picks loaded: "
        f"{len(picks)}"
    )

    print(
        f"College team profiles created: "
        f"{len(processed)}"
    )

    print()

    print(
        "TOP 15 TEAMS BY DRAFTED PLAYER COUNT"
    )

    print("-" * 70)

    by_count = sorted(
        processed,
        key=lambda team:
            (
                team[
                    "drafted_count"
                ],
                team[
                    "draft_capital"
                ],
            ),
        reverse=True,
    )

    for team in by_count[:15]:

        print(
            f"{team['team']}: "
            f"drafted="
            f"{team['drafted_count']}, "
            f"R1="
            f"{team['round_1_count']}, "
            f"top50="
            f"{team['top_50_count']}, "
            f"top100="
            f"{team['top_100_count']}, "
            f"capital="
            f"{team['draft_capital']:.2f}, "
            f"grade_sum="
            f"{team['pre_draft_grade_sum']:.1f}"
        )

    print()

    print(
        "TOP 15 TEAMS BY DRAFT CAPITAL"
    )

    print("-" * 70)

    by_capital = sorted(
        processed,
        key=lambda team:
            team[
                "draft_capital"
            ],
        reverse=True,
    )

    for team in by_capital[:15]:

        print(
            f"{team['team']}: "
            f"capital="
            f"{team['draft_capital']:.2f}, "
            f"drafted="
            f"{team['drafted_count']}, "
            f"R1="
            f"{team['round_1_count']}, "
            f"Day2="
            f"{team['day_2_count']}, "
            f"top50="
            f"{team['top_50_count']}, "
            f"QB="
            f"{team['qb_drafted_count']}"
        )

    print()

    print(
        "TEAMS LOSING DRAFTED QUARTERBACKS"
    )

    print("-" * 70)

    qb_teams = [
        team
        for team in processed
        if team[
            "qb_drafted_count"
        ] > 0
    ]

    qb_teams.sort(
        key=lambda team:
            (
                team[
                    "qb_round_1_count"
                ],
                team[
                    "draft_capital"
                ],
            ),
        reverse=True,
    )

    for team in qb_teams:

        print(
            f"{team['team']}: "
            f"QB drafted="
            f"{team['qb_drafted_count']}, "
            f"QB R1="
            f"{team['qb_round_1_count']}, "
            f"total drafted="
            f"{team['drafted_count']}, "
            f"capital="
            f"{team['draft_capital']:.2f}"
        )

    print()

    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    calculate_draft_losses()
