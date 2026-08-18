"""
Project Gridiron
2026 Provisional Game Predictions V2

Purpose
-------
Generate provisional 2026 game projections using:

    1. 2026 provisional Project Gridiron power ratings
    2. 2025 V3 rating-to-margin calibration

Inputs
------
data/processed/power_ratings_2026.json
data/raw/games.json
data/processed/game_margin_calibration_v3_2025.json

Output
------
data/processed/provisional_game_predictions_2026.json

Model
-----
Projected home margin:

    rating_gap_coefficient
        * (home_rating - away_rating)
        +
    home_field_advantage
        * home_field_indicator

Where:

    home_field_indicator = 0 for neutral-site games
    home_field_indicator = 1 otherwise

The coefficients are loaded from:

    data/processed/game_margin_calibration_v3_2025.json

Current calibration:

    approximately 0.899 scoreboard points
    per Project Gridiron rating point

    approximately 3.95 points
    of non-neutral home-field advantage

This remains a provisional preseason prediction layer.
It will later be upgraded when full V4 preseason ratings become available.

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

CALIBRATION_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "game_margin_calibration_v3_2025.json"
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

PRE_SEPTEMBER_END_UTC = datetime(
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
    """Parse ISO datetime."""

    if not value:
        return None

    try:

        normalized = (
            str(value)
            .replace(
                "Z",
                "+00:00"
            )
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
    """Build rating lookup by team."""

    lookup = {}

    if not isinstance(
        records,
        list
    ):
        return lookup

    for record in records:

        if not isinstance(
            record,
            dict
        ):
            continue

        team = record.get(
            "team"
        )

        rating = safe_float(
            record.get(
                "power_rating"
            )
        )

        if (
            team
            and
            rating is not None
        ):

            lookup[
                team
            ] = record

    return lookup


def load_calibration():
    """Load V3 margin calibration."""

    if not CALIBRATION_FILE.exists():

        raise FileNotFoundError(
            f"Missing calibration file: "
            f"{CALIBRATION_FILE}"
        )

    data = load_json(
        CALIBRATION_FILE
    )

    model = data.get(
        "model"
    )

    if not isinstance(
        model,
        dict
    ):

        raise ValueError(
            "Calibration file does not contain a model object."
        )

    rating_gap_coefficient = safe_float(
        model.get(
            "rating_gap_coefficient"
        )
    )

    home_field_advantage = safe_float(
        model.get(
            "home_field_advantage"
        )
    )

    if rating_gap_coefficient is None:

        raise ValueError(
            "Calibration rating_gap_coefficient is missing."
        )

    if home_field_advantage is None:

        raise ValueError(
            "Calibration home_field_advantage is missing."
        )

    return {
        "model_version":
            data.get(
                "model_version",
                "game_margin_calibration_v3",
            ),

        "season":
            data.get(
                "season"
            ),

        "games_tested":
            data.get(
                "games_tested"
            ),

        "rating_gap_coefficient":
            rating_gap_coefficient,

        "home_field_advantage":
            home_field_advantage,
    }


def is_fbs_team(
    game,
    side
):
    """Return whether side is classified FBS."""

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
    """Return whether game starts before September 1 UTC."""

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
        PRE_SEPTEMBER_END_UTC
    )


# ============================================================
# PROJECTION MODEL
# ============================================================

def calculate_projected_home_margin(
    home_rating,
    away_rating,
    neutral_site,
    calibration,
):
    """Calculate calibrated projected home margin."""

    rating_gap = (
        home_rating
        -
        away_rating
    )

    home_field_indicator = (
        0.0
        if neutral_site
        else 1.0
    )

    rating_margin = (
        rating_gap
        *
        calibration[
            "rating_gap_coefficient"
        ]
    )

    home_field_margin = (
        home_field_indicator
        *
        calibration[
            "home_field_advantage"
        ]
    )

    projected_home_margin = (
        rating_margin
        +
        home_field_margin
    )

    return {
        "rating_gap":
            rating_gap,

        "rating_margin":
            rating_margin,

        "home_field_indicator":
            home_field_indicator,

        "home_field_margin":
            home_field_margin,

        "projected_home_margin":
            projected_home_margin,
    }


def project_game(
    game,
    rating_lookup,
    calibration,
):
    """Project one 2026 game."""

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

    components = (
        calculate_projected_home_margin(
            home_rating,
            away_rating,
            neutral_site,
            calibration,
        )
    )

    projected_home_margin = components[
        "projected_home_margin"
    ]

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

        "raw_rating_gap":
            round(
                components[
                    "rating_gap"
                ],
                4,
            ),

        "rating_gap_coefficient":
            round(
                calibration[
                    "rating_gap_coefficient"
                ],
                6,
            ),

        "rating_margin_component":
            round(
                components[
                    "rating_margin"
                ],
                4,
            ),

        "home_field_advantage":
            round(
                calibration[
                    "home_field_advantage"
                ],
                4,
            ),

        "home_field_component":
            round(
                components[
                    "home_field_margin"
                ],
                4,
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

        "calibration_model":
            calibration[
                "model_version"
            ],

        "provisional":
            True,
    }


# ============================================================
# BUILD PREDICTIONS
# ============================================================

def build_predictions():
    """Generate calibrated provisional predictions."""

    required_files = [
        RATINGS_FILE,
        GAMES_FILE,
        CALIBRATION_FILE,
    ]

    for path in required_files:

        if not path.exists():

            raise FileNotFoundError(
                f"Missing required file: "
                f"{path}"
            )

    ratings = load_json(
        RATINGS_FILE
    )

    games = load_json(
        GAMES_FILE
    )

    calibration = load_calibration()

    rating_lookup = build_rating_lookup(
        ratings
    )

    predictions = []

    skipped_missing_rating = []

    skipped_non_fbs = 0

    eligible_games = 0

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

        eligible_games += 1

        projection = project_game(
            game,
            rating_lookup,
            calibration,
        )

        if projection is None:

            skipped_missing_rating.append(
                {
                    "game_id":
                        game.get(
                            "id"
                        ),

                    "home":
                        game.get(
                            "homeTeam"
                        ),

                    "away":
                        game.get(
                            "awayTeam"
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

    # ========================================================
    # OUTPUT
    # ========================================================

    print("=" * 80)

    print(
        "PROJECT GRIDIRON 2026 CALIBRATED PROVISIONAL PREDICTIONS"
    )

    print("=" * 80)

    print()

    print(
        "CALIBRATION"
    )

    print("-" * 80)

    print(
        f"Model: "
        f"{calibration['model_version']}"
    )

    print(
        f"2025 games used: "
        f"{calibration['games_tested']}"
    )

    print(
        f"Rating-to-margin coefficient: "
        f"{calibration['rating_gap_coefficient']:.4f}"
    )

    print(
        f"Home-field advantage: "
        f"{calibration['home_field_advantage']:.4f}"
    )

    print()

    print(
        "PREDICTION SUMMARY"
    )

    print("-" * 80)

    print(
        f"Ratings loaded: "
        f"{len(rating_lookup)}"
    )

    print(
        f"Eligible FBS-vs-FBS games: "
        f"{eligible_games}"
    )

    print(
        f"Predictions generated: "
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
            f"  raw rating gap: "
            f"{record['raw_rating_gap']:+.2f}"
        )

        print(
            f"  rating component: "
            f"{record['rating_margin_component']:+.2f}"
        )

        print(
            f"  home-field component: "
            f"{record['home_field_component']:+.2f}"
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
                f"(game_id="
                f"{record['game_id']})"
            )

        print()

    print(
        "Saved to:"
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
