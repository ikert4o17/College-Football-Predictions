"""
Calculate 2024 strength of schedule metrics.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

GAMES_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "historical_games_2024.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "strength_of_schedule_2024.json"
)


def load_games():
    """Load processed 2024 historical games."""

    with GAMES_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def calculate_team_margins(games):
    """Calculate each team's average margin."""

    team_games = {}

    for game in games:

        if game["game_classification"] != "fbs_vs_fbs":
            continue

        home = game["home"]
        away = game["away"]

        home_team = home["team"]
        away_team = away["team"]

        if home_team not in team_games:
            team_games[home_team] = []

        if away_team not in team_games:
            team_games[away_team] = []

        team_games[home_team].append(
            home["margin"]
        )

        team_games[away_team].append(
            away["margin"]
        )

    team_margins = {}

    for team, margins in team_games.items():

        if margins:
            team_margins[team] = (
                sum(margins) / len(margins)
            )

    return team_margins


def calculate_sos(games):
    """Calculate strength of schedule for each team."""

    team_opponents = {}

    for game in games:

        if game["game_classification"] != "fbs_vs_fbs":
            continue

        home_team = game["home"]["team"]
        away_team = game["away"]["team"]

        if home_team not in team_opponents:
            team_opponents[home_team] = []

        if away_team not in team_opponents:
            team_opponents[away_team] = []

        team_opponents[home_team].append(
            away_team
        )

        team_opponents[away_team].append(
            home_team
        )

    team_margins = calculate_team_margins(
        games
    )

    sos_profiles = []

    for team, opponents in team_opponents.items():

        opponent_margins = []

        opponent_details = []

        for opponent in opponents:

            if opponent not in team_margins:
                continue

            margin = team_margins[opponent]

            opponent_margins.append(
                margin
            )

            opponent_details.append(
                {
                    "team": opponent,
                    "margin": margin,
                }
            )

        if not opponent_margins:
            continue

        average_opponent_margin = (
            sum(opponent_margins)
            / len(opponent_margins)
        )

        sos_profiles.append(
            {
                "season": 2024,
                "team": team,
                "sos": {
                    "games": len(opponent_margins),
                    "average_opponent_margin":
                        average_opponent_margin,
                    "opponents":
                        opponent_details,
                },
            }
        )

    sos_profiles.sort(
        key=lambda team: team["team"]
    )

    return sos_profiles


def calculate_strength_of_schedule():
    """Calculate and save 2024 SOS profiles."""

    games = load_games()

    sos_profiles = calculate_sos(
        games
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
            sos_profiles,
            file,
            indent=4
        )

    print(
        f"Calculated SOS profiles for "
        f"{len(sos_profiles)} teams."
    )

    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    calculate_strength_of_schedule()
