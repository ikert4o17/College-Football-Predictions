"""
Project Gridiron
2026 Provisional Game Predictions

Purpose
-------
Generate provisional 2026 game projections using the current
Project Gridiron provisional preseason power ratings.

Inputs
------
data/processed/power_ratings_2026.json
data/raw/games.json

Output
------
data/processed/provisional_game_predictions_2026.json

Current model
-------------
Projected margin:

    home team power rating
    -
    away team power rating
    +
    home-field advantage

Neutral-site games receive no home-field adjustment.

This is a provisional Week 0 / early-season prediction layer.
It will later be replaced or upgraded once the full V4 preseason
ratings and in-season adjustments are available.

Usage
-----
python -m predictions.provisional_2026_predictions
"""

import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# FILES
# ============================================================

RATINGS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "power_ratings_2026.json"
)

GAMES_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "games.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "provisional_game_predictions_2026.json"
)


# ============================================================
# SETTINGS
# ============================================================

SEASON = 2026

HOME_FIELD_ADVANTAGE = 2.5

WEEK_0_END_UTC = datetime(
    2026,
    9,
    1,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)


# ============================================================
# HELPERS
# ============================================================

def load_json(path):
    """Load JSON file."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def safe_float(
    value,
    default=None
):
    """Safely convert value to float."""

    if value is None:
        return default

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return default


def parse_datetime(value):
    """Parse CFBD ISO datetime."""

    if not value:
        return None

    try:

        normalized = value.replace(
            "Z",
            "+00:00"
        )

        parsed = datetime.fromisoformat(
            normalized
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    except ValueError:
        return None


def build_rating_lookup(records):
    """Build rating lookup by team name."""

    lookup = {}

    if not isinstance(records, list):
        return lookup

    for record in records:

        if not isinstance(record, dict):
            continue

        team = record.get(
            "team"
        )

        rating = safe_float(
            record.get(
                "power_rating"
            )
        )

        if not team:
            continue

        if rating is None:
            continue

        lookup[
            team
        ] = record

    return lookup


def is_fbs_team(game, side):
    """Return whether game side is classified as FBS."""

    classification = game.get(
        f"{side}Classification"
    )

    if classification is None:
        return False

    return (
        str(
            classification
        )
        .strip()
        .lower()
        ==
        "fbs"
    )


def is_pre_september_game(game):
    """Return whether game occurs before September 1 UTC."""

    start_date = parse_datetime(
        game.get(
            "startDate"
        )
    )

    if start_date is None:
        return False

    return (
        start_date
        <
        WEEK_0_END_UTC
    )


# ============================================================
# MODEL
# ============================================================

def project_game(
    game,
    rating_lookup
):
    """Project one game."""

    home_team = game.get(
        "homeTeam"
    )

    away_team = game.get(
        "awayTeam"
    )

    if not home_team or not away_team:
        return None

    home_record = rating_lookup.get(
        home_team
    )

    away_record = rating_lookup.get(
        away_team
    )

    if home_record is None:
        return None

    if away_record is None:
        return None

    home_rating = safe_float(
        home_record.get(
            "power_rating"
        )
    )

    away_rating = safe_float(
        away_record.get(
            "power_rating"
        )
    )

    if (
        home_rating is None
        or
        away_rating is None
    ):
        return None

    neutral_site = bool(
        game.get(
            "neutralSite"
        )
    )

    home_field = (
        0.0
        if neutral_site
        else HOME_FIELD_ADVANTAGE
    )

    projected_home_margin = (
        home_rating
        -
        away_rating
        +
        home_field
    )

    if projected_home_margin > 0:

        projected_winner = home_team

        projected_margin = (
            projected_home_margin
        )

    elif projected_home_margin < 0:

        projected_winner = away_team

        projected_margin = (
            -projected_home_margin
        )

    else:

        projected_winner = None

        projected_margin = 0.0

    return {
        "season":
            SEASON,

        "game_id":
            game.get(
                "id"
            ),

        "week":
            game.get(
                "week"
            ),

        "start_date":
            game.get(
                "startDate"
            ),

        "start_time_tbd":
            game.get(
                "startTimeTBD"
            ),

        "neutral_site":
            neutral_site,

        "venue":
            game.get(
                "venue"
            ),

        "home_team":
            home_team,

        "away_team":
            away_team,

        "home_rating":
            round(
                home_rating,
                4,
            ),

        "away_rating":
            round(
                away_rating,
                4,
            ),

        "home_field_advantage":
            round(
                home_field,
                2,
            ),

        "projected_home_margin":
            round(
                projected_home_margin,
                2,
            ),

        "projected_winner":
            projected_winner,

        "projected_margin":
            round(
                projected_margin,
                2,
            ),

        "rating_model":
            home_record.get(
                "model_version",
                "2026_preseason_provisional_v1",
            ),

        "provisional":
            True,
    }


# ============================================================
# BUILD PREDICTIONS
# ============================================================

def build_predictions():
    """Generate provisional 2026 predictions."""

    if not RATINGS_FILE.exists():

        raise FileNotFoundError(
            f"Missing ratings file: "
            f"{RATINGS_FILE}"
        )

    if not GAMES_FILE.exists():

        raise FileNotFoundError(
            f"Missing games file: "
            f"{GAMES_FILE}"
        )

    ratings = load_json(
        RATINGS_FILE
    )

    games = load_json(
        GAMES_FILE
    )

    rating_lookup = build_rating_lookup(
        ratings
    )

    predictions = []

    skipped_missing_rating = []

    skipped_non_fbs = 0

    for game in games:

        if not isinstance(
            game,
            dict
        ):
            continue

        if game.get(
            "season"
        ) != SEASON:
            continue

        if game.get(
            "seasonType"
        ) != "regular":
            continue

        if not is_pre_september_game(
            game
        ):
            continue

        # Current provisional model only predicts
        # FBS vs FBS games.

        if not (
            is_fbs_team(
                game,
                "home"
            )
            and
            is_fbs_team(
                game,
                "away"
            )
        ):

            skipped_non_fbs += 1
            continue

        projection = project_game(
            game,
            rating_lookup,
        )

        if projection is None:

            skipped_missing_rating.append(
                {
                    "home":
                        game.get(
                            "homeTeam"
                        ),

                    "away":
                        game.get(
                            "awayTeam"
                        ),

                    "game_id":
                        game.get(
                            "id"
                        ),
                }
            )

            continue

        predictions.append(
            projection
        )

    predictions.sort(
        key=lambda record:
            (
                record.get(
                    "start_date"
                )
                or "",
                record.get(
                    "game_id"
                )
                or 0,
            )
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            predictions,
            file,
            indent=4,
        )

    print("=" * 80)

    print(
        "PROJECT GRIDIRON 2026 PROVISIONAL GAME PREDICTIONS"
    )

    print("=" * 80)

    print()

    print(
        f"Ratings loaded: "
        f"{len(rating_lookup)}"
    )

    print(
        f"Eligible FBS vs FBS games before Sept. 1: "
        f"{len(predictions)}"
    )

    print(
        f"Non-FBS matchups skipped: "
        f"{skipped_non_fbs}"
    )

    print(
        f"Games skipped for missing ratings: "
        f"{len(skipped_missing_rating)}"
    )

    print()

    print(
        "WEEK 0 / PRE-SEPTEMBER PROJECTIONS"
    )

    print("-" * 80)

    for record in predictions:

        winner = (
            record[
                "projected_winner"
            ]
            or "Pick'em"
        )

        print(
            f"{record['away_team']} "
            f"@ "
            f"{record['home_team']}"
        )

        print(
            f"  ratings: "
            f"{record['away_rating']:.2f} "
            f"vs "
            f"{record['home_rating']:.2f}"
        )

        print(
            f"  HFA: "
            f"{record['home_field_advantage']:+.2f}"
        )

        print(
            f"  projection: "
            f"{winner} "
            f"by "
            f"{record['projected_margin']:.1f}"
        )

        print()

    if skipped_missing_rating:

        print(
            "MISSING-RATING MATCHUPS"
        )

        print("-" * 80)

        for record in skipped_missing_rating:

            print(
                f"{record['away']} "
                f"@ "
                f"{record['home']} "
                f"(game_id={record['game_id']})"
            )

        print()

    print(
        f"Saved to:"
    )

    print(
        OUTPUT_FILE
    )

    return predictions


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    build_predictions()
