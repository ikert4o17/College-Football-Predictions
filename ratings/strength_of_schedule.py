"""
Calculate strength of schedule from team results.

Usage:
    python -m ratings.strength_of_schedule 2023
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def results_file(year):
    return PROJECT_ROOT / "data" / "processed" / f"team_results_{year}.json"


def output_file(year):
    return PROJECT_ROOT / "data" / "processed" / f"strength_of_schedule_{year}.json"


def load_results(year):
    source = results_file(year)
    if not source.exists():
        raise FileNotFoundError(f"Team results file not found: {source}")
    with source.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_team_lookup(results):
    return {team["team"]: team for team in results}


def calculate_sos(team, team_lookup):
    opponent_margins = []
    for opponent in team["opponents"]:
        if opponent["game_classification"] != "fbs_vs_fbs":
            continue
        opponent_data = team_lookup.get(opponent["team"])
        if opponent_data is not None:
            opponent_margins.append(opponent_data["point_margin_per_game"])

    if not opponent_margins:
        return {"games": 0, "average_opponent_margin": 0, "opponents": []}

    return {
        "games": len(opponent_margins),
        "average_opponent_margin": sum(opponent_margins) / len(opponent_margins),
        "opponents": [
            {"team": opponent["team"], "margin": team_lookup[opponent["team"]]["point_margin_per_game"]}
            for opponent in team["opponents"]
            if opponent["game_classification"] == "fbs_vs_fbs" and opponent["team"] in team_lookup
        ],
    }


def calculate_all_sos(year=2025):
    results = load_results(year)
    team_lookup = build_team_lookup(results)
    sos_results = []
    for team in results:
        if team["fbs_games"] == 0:
            continue
        sos_results.append({"season": year, "team": team["team"], "sos": calculate_sos(team, team_lookup)})

    sos_results.sort(key=lambda team: team["sos"]["average_opponent_margin"], reverse=True)
    destination = output_file(year)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as file:
        json.dump(sos_results, file, indent=4)
    print(f"Calculated SOS for {len(sos_results)} FBS teams in {year}.")
    print(f"Saved to {destination}")


if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    calculate_all_sos(year)
