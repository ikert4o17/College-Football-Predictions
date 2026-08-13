"""
Team data definitions.

This module provides the structure used to represent
college football teams throughout the project.
"""


def create_team(
    team_id,
    name,
    abbreviation,
    conference,
    fbs_status="full",
):
    """Create a standardized team record."""

    return {
        "id": team_id,
        "name": name,
        "abbreviation": abbreviation,
        "conference": conference,
        "fbs_status": fbs_status,
    }
