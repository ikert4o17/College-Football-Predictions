"""
Calculate initial team strength metrics from historical performance.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "historical_stats_2025.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "team_strength_2025.json"
)


def calculate_offense(stats):
    """Calculate offensive strength."""

    return {
        "rushing_yards_per_game":
            stats.get("rushingYardsPerGame", 0),

        "passing_yards_per_game":
            stats.get("passingYardsPerGame", 0),

        "total_yards_per_game":
            stats.get("totalYardsPerGame", 0),

        "yards_per_rush":
            stats.get("yardsPerRush", 0),

        "net_yards_per_pass":
            stats.get("netYardsPerPass", 0),

        "third_down_conversion":
            stats.get("thirdDownConversionRate", 0),
    }


def calculate_defense(stats):
    """Calculate defensive strength."""

    return {
        "rushing_yards_allowed_per_game":
            stats.get("rushingYardsAllowedPerGame", 0),

        "passing_yards_allowed_per_game":
            stats.get("passingYardsAllowedPerGame", 0),

        "total_yards_allowed_per_game":
            stats.get("totalYardsAllowedPerGame", 0),

        "third_down_defense":
            stats.get("thirdDownDefenseRate", 0),

        "sacks_per_game":
            stats.get("sacksPerGame", 0),

        "tackles_for_loss_per_game":
            stats.get("tacklesForLoss", 0)
            / max(stats.get("games", 1), 1),
    }


def calculate_turnovers(stats):
    """Calculate turnover strength."""

    return {
        "turnovers_per_game":
            stats.get("turnoversPerGame", 0),

        "turnovers_forced_per_game":
            stats.get("turnoversForcedPerGame", 0),

        "turnover_margin_per_game":
            stats.get("turnoverMarginPerGame", 0),
    }


def calculate_discipline(stats):
    """Calculate penalty and discipline metrics."""

    return {
        "penalties_per_game":
            stats.get("penaltiesPerGame", 0),

        "penalty_yards_per_game":
            stats.get("penaltyYardsPerGame", 0),
    }


def calculate_team_strength(team):
    """Create a complete team strength profile."""

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


def calculate_all_teams():
    """Calculate strength metrics for every team."""

    with INPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        teams = json.load(file)

    strengths = []

    for team in teams:
        strengths.append(
            calculate_team_strength(team)
        )

    strengths.sort(
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
            strengths,
            file,
            indent=4
        )

    print(
        f"Calculated strength metrics for "
        f"{len(strengths)} teams."
    )

    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    calculate_all_teams()
