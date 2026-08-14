"""
Process historical CFBD team statistics into model-ready team profiles.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "historical_stats" / "2024.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "historical_stats_2024.json"


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

    # Offensive production
    stats["rushingYardsPerGame"] = per_game(
        stats.get("rushingYards", 0)
    )

    stats["passingYardsPerGame"] = per_game(
        stats.get("netPassingYards", 0)
    )

    stats["totalYardsPerGame"] = per_game(
        stats.get("totalYards", 0)
    )

    stats["rushingAttemptsPerGame"] = per_game(
        stats.get("rushingAttempts", 0)
    )

    # Defensive production
    stats["rushingYardsAllowedPerGame"] = per_game(
        stats.get("rushingYardsOpponent", 0)
    )

    stats["passingYardsAllowedPerGame"] = per_game(
        stats.get("netPassingYardsOpponent", 0)
    )

    stats["totalYardsAllowedPerGame"] = per_game(
        stats.get("totalYardsOpponent", 0)
    )

    # Efficiency
    rushing_attempts = stats.get("rushingAttempts", 0)

    if rushing_attempts:
        stats["yardsPerRush"] = (
            stats.get("rushingYards", 0)
            / rushing_attempts
        )
    else:
        stats["yardsPerRush"] = 0

    pass_attempts = stats.get("passAttempts", 0)

    if pass_attempts:
        stats["netYardsPerPass"] = (
            stats.get("netPassingYards", 0)
            / pass_attempts
        )
    else:
        stats["netYardsPerPass"] = 0

    # Third down
    third_downs = stats.get("thirdDowns", 0)

    if third_downs:
        stats["thirdDownConversionRate"] = (
            stats.get("thirdDownConversions", 0)
            / third_downs
        )
    else:
        stats["thirdDownConversionRate"] = 0

    opponent_third_downs = stats.get(
        "thirdDownsOpponent",
        0
    )

    if opponent_third_downs:
        stats["thirdDownDefenseRate"] = (
            stats.get("thirdDownConversionsOpponent", 0)
            / opponent_third_downs
        )
    else:
        stats["thirdDownDefenseRate"] = 0

    # Turnovers
    stats["turnoversPerGame"] = per_game(
        stats.get("turnovers", 0)
    )

    stats["turnoversForcedPerGame"] = per_game(
        stats.get("turnoversOpponent", 0)
    )

    stats["turnoverMarginPerGame"] = (
        stats.get("turnoversOpponent", 0)
        - stats.get("turnovers", 0)
    ) / games

    # Penalties
    stats["penaltiesPerGame"] = per_game(
        stats.get("penalties", 0)
    )

    stats["penaltyYardsPerGame"] = per_game(
        stats.get("penaltyYards", 0)
    )

    # Sacks
    stats["sacksPerGame"] = per_game(
        stats.get("sacks", 0)
    )

    stats["sacksAllowedPerGame"] = per_game(
        stats.get("sacksOpponent", 0)
    )

    return profile


def process_stats():
    """Process the historical statistics file."""

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        raw_stats = json.load(file)

    team_profiles = build_team_profiles(raw_stats)

    processed_profiles = []

    for profile in team_profiles.values():
        profile = calculate_metrics(profile)
        processed_profiles.append(profile)

    processed_profiles.sort(
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
            processed_profiles,
            file,
            indent=4
        )

    print(
        f"Processed {len(processed_profiles)} teams."
    )

    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    process_stats()
