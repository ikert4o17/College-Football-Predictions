"""
Standardized college football team data structure.
"""


def create_team(
    team_id,
    name,
    abbreviation,
    conference,
    mascot=None,
    stadium=None,
    city=None,
    state=None,
    timezone=None,
    elevation=None,
    capacity=None,
    grass=None,
    dome=None,
):
    """Create a standardized team record."""

    return {
        "team_id": team_id,
        "name": name,
        "abbreviation": abbreviation,
        "conference": conference,
        "mascot": mascot,
        "stadium": stadium,
        "city": city,
        "state": state,
        "timezone": timezone,
        "elevation": elevation,
        "capacity": capacity,
        "grass": grass,
        "dome": dome,
    }
