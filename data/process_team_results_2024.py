"""
Process 2024 historical games into team-level result profiles.
"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "historical_games_2024.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "team_results_2024.json"
)


def create_team_profile(team):
    """Create an empty result profile for a team."""

    return {
        "season": 2024,
        "team": team,
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


def process_games():
    """Build team result profiles from historical games."""

    with INPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        games = json.load(file)

    teams = {}

    for game in games:

        home = game["home"]
        away = game["away"]

        home_team = home["team"]
        away_team = away["team"]

        if home_team not in teams:
            teams[home_team] = create_team_profile(
                home_team
            )

        if away_team not in teams:
            teams[away_team] = create_team_profile(
                away_team
            )

        home_profile = teams[home_team]
        away_profile = teams[away_team]

        # --------------------------------------------------
        # Determine game classification
        # --------------------------------------------------

        classification = game["game_classification"]

        if classification == "fbs_vs_fbs":
            home_fbs_game = True
            away_fbs_game = True
        elif classification == "fbs_vs_lower":
            home_fbs_game = (
                home["classification"] == "fbs"
            )
            away_fbs_game = (
                away["classification"] == "fbs"
            )
        else:
            home_fbs_game = False
            away_fbs_game = False

        # --------------------------------------------------
        # HOME TEAM
        # --------------------------------------------------

        home_profile["games"] += 1

        home_profile["points_scored"] += home["points"]
        home_profile["points_allowed"] += away["points"]

        home_profile["point_margin"] += home["margin"]

        if game["neutral_site"]:
            home_profile["neutral_games"] += 1
        else:
            home_profile["home_games"] += 1

        if home_fbs_game:
            home_profile["fbs_games"] += 1
        else:
            home_profile["lower_division_games"] += 1

        if home["margin"] > 0:
            home_profile["wins"] += 1
        elif home["margin"] < 0:
            home_profile["losses"] += 1
        else:
            home_profile["ties"] += 1

        home_profile["opponents"].append(
            {
                "team": away["team"],
                "team_id": away["team_id"],
                "points_scored": home["points"],
                "points_allowed": away["points"],
                "margin": home["margin"],
                "home": True,
                "neutral": game["neutral_site"],
                "game_classification": classification,
            }
        )

        # --------------------------------------------------
        # AWAY TEAM
        # --------------------------------------------------

        away_profile["games"] += 1

        away_profile["points_scored"] += away["points"]
        away_profile["points_allowed"] += home["points"]

        away_profile["point_margin"] += away["margin"]

        if game["neutral_site"]:
            away_profile["neutral_games"] += 1
        else:
            away_profile["away_games"] += 1

        if away_fbs_game:
            away_profile["fbs_games"] += 1
        else:
            away_profile["lower_division_games"] += 1

        if away["margin"] > 0:
            away_profile["wins"] += 1
        elif away["margin"] < 0:
            away_profile["losses"] += 1
        else:
            away_profile["ties"] += 1

        away_profile["opponents"].append(
            {
                "team": home["team"],
                "team_id": home["team_id"],
                "points_scored": away["points"],
                "points_allowed": home["points"],
                "margin": away["margin"],
                "home": False,
                "neutral": game["neutral_site"],
                "game_classification": classification,
            }
        )

    # ------------------------------------------------------
    # Calculate normalized metrics
    # ------------------------------------------------------

    for profile in teams.values():

        games_played = profile["games"]

        if games_played == 0:
            continue

        profile["points_scored_per_game"] = (
            profile["points_scored"]
            / games_played
        )

        profile["points_allowed_per_game"] = (
            profile["points_allowed"]
            / games_played
        )

        profile["point_margin_per_game"] = (
            profile["point_margin"]
            / games_played
        )

        profile["win_percentage"] = (
            profile["wins"]
            / games_played
        )

    # ------------------------------------------------------
    # Sort teams alphabetically
    # ------------------------------------------------------

    processed_profiles = list(
        teams.values()
    )

    processed_profiles.sort(
        key=lambda team: team["team"]
    )

    # ------------------------------------------------------
    # Save output
    # ------------------------------------------------------

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
        f"Processed {len(processed_profiles)} team result profiles."
    )

    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    process_games()
