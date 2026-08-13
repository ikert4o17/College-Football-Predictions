"""
Build team-level 2025 results from historical games.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "historical_games_2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "team_results_2025.json"
)


def create_team_record(team_name):
    """Create an empty team results record."""

    return {
        "season": 2025,
        "team": team_name,
        "games": 0,
        "wins": 0,
        "losses": 0,
        "ties": 0,
        "points_scored": 0,
        "points_allowed": 0,
        "point_margin": 0,
        "home_games": 0,
        "away_games": 0,
        "neutral_games": 0,
        "fbs_games": 0,
        "lower_division_games": 0,
        "opponents": [],
    }


def add_game_to_team(
    record,
    game,
    team_side,
    opponent_side,
):
    """Add one game to a team's season record."""

    team = game[team_side]
    opponent = game[opponent_side]

    team_points = team["points"]
    opponent_points = opponent["points"]

    record["games"] += 1

    record["points_scored"] += team_points
    record["points_allowed"] += opponent_points

    margin = team_points - opponent_points

    record["point_margin"] += margin

    if margin > 0:
        record["wins"] += 1
    elif margin < 0:
        record["losses"] += 1
    else:
        record["ties"] += 1

    if game["neutral_site"]:
        record["neutral_games"] += 1
    elif team_side == "home":
        record["home_games"] += 1
    else:
        record["away_games"] += 1

    if (
        game["game_classification"]
        == "fbs_vs_fbs"
    ):
        record["fbs_games"] += 1
    else:
        record["lower_division_games"] += 1

    record["opponents"].append(
        {
            "team": opponent["team"],
            "team_id": opponent["team_id"],
            "points_scored": team_points,
            "points_allowed": opponent_points,
            "margin": margin,
            "home": team_side == "home",
            "neutral": game["neutral_site"],
            "game_classification":
                game["game_classification"],
        }
    )


def calculate_averages(record):
    """Calculate per-game results."""

    games = record["games"]

    if games == 0:
        return record

    record["points_scored_per_game"] = (
        record["points_scored"] / games
    )

    record["points_allowed_per_game"] = (
        record["points_allowed"] / games
    )

    record["point_margin_per_game"] = (
        record["point_margin"] / games
    )

    record["win_percentage"] = (
        record["wins"] / games
    )

    return record


def process_results():
    """Process historical games into team results."""

    with INPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        games = json.load(file)

    teams = {}

    for game in games:

        home_team = game["home"]["team"]
        away_team = game["away"]["team"]

        if home_team not in teams:
            teams[home_team] = create_team_record(
                home_team
            )

        if away_team not in teams:
            teams[away_team] = create_team_record(
                away_team
            )

        add_game_to_team(
            teams[home_team],
            game,
            "home",
            "away",
        )

        add_game_to_team(
            teams[away_team],
            game,
            "away",
            "home",
        )

    results = []

    for team in teams.values():
        results.append(
            calculate_averages(team)
        )

    results.sort(
        key=lambda team: team["team"]
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
            results,
            file,
            indent=4
        )

    print(
        f"Processed results for "
        f"{len(results)} teams."
    )

    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    process_results()
