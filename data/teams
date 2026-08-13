"""
FBS Team Database

Master team definitions used throughout the model.
"""

from data.team_data import create_team


TEAMS = {
    "ohio_state": create_team(
        team_id="ohio_state",
        name="Ohio State",
        abbreviation="OSU",
        conference="Big Ten",
    ),
}


def get_team(team_id):
    """Return a team by its unique ID."""
    return TEAMS.get(team_id)


def get_all_teams():
    """Return all FBS teams."""
    return TEAMS


def get_team_count():
    """Return the number of teams currently in the database."""
    return len(TEAMS)
