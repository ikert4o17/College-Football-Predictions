"""
Calculate 2025 Strength of Schedule.

SOS is based on the average 2025 point
margin per game of each team's FBS opponents.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RESULTS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "team_results_2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "strength_of_schedule_2025.json"
)


def load_results():
    """Load 2025 team results."""

    with RESULTS_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def build_team_lookup(results):
    """Create a team-name lookup."""

    return {
        team["team"]: team
        for team in results
    }


def calculate_sos(team, team_lookup):
    """Calculate opponent strength for one team."""

    opponent_margins = []

    for opponent in team["opponents"]:

        if opponent["game_classification"] != "fbs_vs_fbs":
            continue

        opponent_name = opponent["team"]

        opponent_data = team_lookup.get(
            opponent_name
        )

        if opponent_data is None:
            continue

        opponent_margins.append(
            opponent_data["point_margin_per_game"]
        )

    if not opponent_margins:
        return {
            "games": 0,
            "average_opponent_margin": 0,
            "opponents": [],
        }

    return {
        "games": len(opponent_margins),
        "average_opponent_margin":
            sum(opponent_margins)
            / len(opponent_margins),
        "opponents": [
            {
                "team": opponent["team"],
                "margin":
                    team_lookup[
                        opponent["team"]
                    ]["point_margin_per_game"],
            }
            for opponent in team["opponents"]
            if (
                opponent["game_classification"]
                == "fbs_vs_fbs"
                and opponent["team"]
                in team_lookup
            )
        ],
    }


def calculate_all_sos():
    """Calculate SOS for every team."""

    results = load_results()

    team_lookup = build_team_lookup(results)

    sos_results = []

    for team in results:

        # Only calculate ratings for FBS teams.
        if team["fbs_games"] == 0:
            continue

        sos = calculate_sos(
            team,
            team_lookup
        )

        sos_results.append(
            {
                "season": 2025,
                "team": team["team"],
                "sos": sos,
            }
        )

    sos_results.sort(
        key=lambda team: team["sos"]["average_opponent_margin"],
        reverse=True,
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
            sos_results,
            file,
            indent=4
        )

    print(
        f"Calculated SOS for "
        f"{len(sos_results)} FBS teams."
    )

    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    calculate_all_sos()
