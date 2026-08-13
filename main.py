"""
College Football Predictions Model

Main application entry point.
"""

from data.teams import get_all_teams, get_team_count


def main():
    """Run the application."""

    teams = get_all_teams()

    print("College Football Predictions Model")
    print("----------------------------------")
    print(f"Teams loaded: {get_team_count()}")

    for team in teams.values():
        print(f"- {team['name']} ({team['abbreviation']})")


if __name__ == "__main__":
    main()
