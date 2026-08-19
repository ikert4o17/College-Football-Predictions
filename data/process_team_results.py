"""
Build team-level results from processed historical games.

Usage:
    python -m data.process_team_results 2023
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def input_file(year):
    return PROJECT_ROOT / "data" / "processed" / f"historical_games_{year}.json"


def output_file(year):
    return PROJECT_ROOT / "data" / "processed" / f"team_results_{year}.json"


def create_team_record(team_name, year):
    return {
        "season": year,
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


def add_game_to_team(record, game, team_side, opponent_side):
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

    if game["game_classification"] == "fbs_vs_fbs":
        record["fbs_games"] += 1
    else:
        record["lower_division_games"] += 1

    record["opponents"].append({
        "team": opponent["team"],
        "team_id": opponent["team_id"],
        "points_scored": team_points,
        "points_allowed": opponent_points,
        "margin": margin,
        "home": team_side == "home",
        "neutral": game["neutral_site"],
        "game_classification": game["game_classification"],
    })


def calculate_averages(record):
    games = record["games"]
    if games == 0:
        return record
    record["points_scored_per_game"] = record["points_scored"] / games
    record["points_allowed_per_game"] = record["points_allowed"] / games
    record["point_margin_per_game"] = record["point_margin"] / games
    record["win_percentage"] = record["wins"] / games
    return record


def process_results(year=2025):
    source = input_file(year)
    destination = output_file(year)
    if not source.exists():
        raise FileNotFoundError(f"Processed historical games not found: {source}")

    with source.open("r", encoding="utf-8") as file:
        games = json.load(file)

    teams = {}
    for game in games:
        home_team = game["home"]["team"]
        away_team = game["away"]["team"]
        if home_team not in teams:
            teams[home_team] = create_team_record(home_team, year)
        if away_team not in teams:
            teams[away_team] = create_team_record(away_team, year)
        add_game_to_team(teams[home_team], game, "home", "away")
        add_game_to_team(teams[away_team], game, "away", "home")

    results = [calculate_averages(team) for team in teams.values()]
    results.sort(key=lambda team: team["team"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=4)

    print(f"Processed results for {len(results)} teams in {year}.")
    print(f"Saved to {destination}")


if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    process_results(year)
