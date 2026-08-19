"""
Calculate team strength metrics from historical performance.

Usage:
    python -m ratings.team_strength 2023
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def input_file(year):
    return PROJECT_ROOT / "data" / "processed" / f"historical_stats_{year}.json"


def output_file(year):
    return PROJECT_ROOT / "data" / "processed" / f"team_strength_{year}.json"


def calculate_offense(stats):
    return {
        "rushing_yards_per_game": stats.get("rushingYardsPerGame", 0),
        "passing_yards_per_game": stats.get("passingYardsPerGame", 0),
        "total_yards_per_game": stats.get("totalYardsPerGame", 0),
        "yards_per_rush": stats.get("yardsPerRush", 0),
        "net_yards_per_pass": stats.get("netYardsPerPass", 0),
        "third_down_conversion": stats.get("thirdDownConversionRate", 0),
    }


def calculate_defense(stats):
    return {
        "rushing_yards_allowed_per_game": stats.get("rushingYardsAllowedPerGame", 0),
        "passing_yards_allowed_per_game": stats.get("passingYardsAllowedPerGame", 0),
        "total_yards_allowed_per_game": stats.get("totalYardsAllowedPerGame", 0),
        "third_down_defense": stats.get("thirdDownDefenseRate", 0),
        "sacks_per_game": stats.get("sacksPerGame", 0),
        "tackles_for_loss_per_game": stats.get("tacklesForLoss", 0) / max(stats.get("games", 1), 1),
    }


def calculate_turnovers(stats):
    return {
        "turnovers_per_game": stats.get("turnoversPerGame", 0),
        "turnovers_forced_per_game": stats.get("turnoversForcedPerGame", 0),
        "turnover_margin_per_game": stats.get("turnoverMarginPerGame", 0),
    }


def calculate_discipline(stats):
    return {
        "penalties_per_game": stats.get("penaltiesPerGame", 0),
        "penalty_yards_per_game": stats.get("penaltyYardsPerGame", 0),
    }


def calculate_team_strength(team):
    stats = team["stats"]
    return {
        "season": team["season"],
        "team": team["team"],
        "conference": team["conference"],
        "games": stats.get("games", 0),
        "offense": calculate_offense(stats),
        "defense": calculate_defense(stats),
        "turnovers": calculate_turnovers(stats),
        "discipline": calculate_discipline(stats),
    }


def calculate_all_teams(year=2025):
    source = input_file(year)
    destination = output_file(year)
    if not source.exists():
        raise FileNotFoundError(f"Historical stats input not found: {source}")
    with source.open("r", encoding="utf-8") as file:
        teams = json.load(file)
    strengths = [calculate_team_strength(team) for team in teams]
    strengths.sort(key=lambda team: team["team"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as file:
        json.dump(strengths, file, indent=4)
    print(f"Calculated strength metrics for {len(strengths)} teams in {year}.")
    print(f"Saved to {destination}")


if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    calculate_all_teams(year)
