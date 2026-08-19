"""
Process historical CFBD team statistics into model-ready team profiles.

Usage:
    python -m data.process_historical_stats 2023
    python -m data.process_historical_stats 2024
    python -m data.process_historical_stats 2025
"""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def input_file(year):
    return PROJECT_ROOT / "data" / "raw" / "historical_stats" / f"{year}.json"


def output_file(year):
    return PROJECT_ROOT / "data" / "processed" / f"historical_stats_{year}.json"


def build_team_profiles(stats):
    """Convert CFBD stat records into one profile per team."""
    teams = {}
    for record in stats:
        team_name = record["team"]
        stat_name = record["statName"]
        stat_value = record["statValue"]
        if team_name not in teams:
            teams[team_name] = {
                "season": record["season"],
                "team": team_name,
                "conference": record["conference"],
                "stats": {},
            }
        teams[team_name]["stats"][stat_name] = stat_value
    return teams


def calculate_metrics(profile):
    """Calculate normalized and efficiency metrics."""
    stats = profile["stats"]
    games = stats.get("games", 0)
    if games == 0:
        return profile

    def per_game(value):
        return value / games

    stats["rushingYardsPerGame"] = per_game(stats.get("rushingYards", 0))
    stats["passingYardsPerGame"] = per_game(stats.get("netPassingYards", 0))
    stats["totalYardsPerGame"] = per_game(stats.get("totalYards", 0))
    stats["rushingAttemptsPerGame"] = per_game(stats.get("rushingAttempts", 0))
    stats["rushingYardsAllowedPerGame"] = per_game(stats.get("rushingYardsOpponent", 0))
    stats["passingYardsAllowedPerGame"] = per_game(stats.get("netPassingYardsOpponent", 0))
    stats["totalYardsAllowedPerGame"] = per_game(stats.get("totalYardsOpponent", 0))

    rushing_attempts = stats.get("rushingAttempts", 0)
    stats["yardsPerRush"] = stats.get("rushingYards", 0) / rushing_attempts if rushing_attempts else 0

    pass_attempts = stats.get("passAttempts", 0)
    stats["netYardsPerPass"] = stats.get("netPassingYards", 0) / pass_attempts if pass_attempts else 0

    third_downs = stats.get("thirdDowns", 0)
    stats["thirdDownConversionRate"] = stats.get("thirdDownConversions", 0) / third_downs if third_downs else 0

    opponent_third_downs = stats.get("thirdDownsOpponent", 0)
    stats["thirdDownDefenseRate"] = stats.get("thirdDownConversionsOpponent", 0) / opponent_third_downs if opponent_third_downs else 0

    stats["turnoversPerGame"] = per_game(stats.get("turnovers", 0))
    stats["turnoversForcedPerGame"] = per_game(stats.get("turnoversOpponent", 0))
    stats["turnoverMarginPerGame"] = (stats.get("turnoversOpponent", 0) - stats.get("turnovers", 0)) / games
    stats["penaltiesPerGame"] = per_game(stats.get("penalties", 0))
    stats["penaltyYardsPerGame"] = per_game(stats.get("penaltyYards", 0))
    stats["sacksPerGame"] = per_game(stats.get("sacks", 0))
    stats["sacksAllowedPerGame"] = per_game(stats.get("sacksOpponent", 0))
    return profile


def process_stats(year=2025):
    source = input_file(year)
    destination = output_file(year)
    if not source.exists():
        raise FileNotFoundError(f"Historical stats file not found: {source}")

    with source.open("r", encoding="utf-8") as file:
        raw_stats = json.load(file)

    team_profiles = build_team_profiles(raw_stats)
    processed_profiles = [calculate_metrics(profile) for profile in team_profiles.values()]
    processed_profiles.sort(key=lambda team: team["team"])

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as file:
        json.dump(processed_profiles, file, indent=4)

    print(f"Processed {len(processed_profiles)} teams for {year}.")
    print(f"Saved to {destination}")


if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    process_stats(year)
