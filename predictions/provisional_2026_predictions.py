"""
Project Gridiron
2026 Provisional Game Predictions V3

Purpose
-------
Generate provisional 2026 game projections using:

    1. 2026 provisional Project Gridiron power ratings
    2. 2025 V3 margin calibration
    3. 2025 game-total calibration

Outputs
-------
For each eligible game:

    - projected spread
    - projected total
    - projected home score
    - projected away score

Inputs
------
data/processed/power_ratings_2026.json
data/raw/games.json
data/processed/game_margin_calibration_v3_2025.json
data/processed/game_total_calibration_2025.json

Output
------
data/processed/provisional_game_predictions_2026.json

Usage
-----
python -m predictions.provisional_2026_predictions

This remains a provisional preseason model.
It will later be upgraded when full V4 preseason ratings are available.
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

MARGIN_CALIBRATION_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "game_margin_calibration_v3_2025.json"
)

TOTAL_CALIBRATION_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "game_total_calibration_2025.json"
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

        if not team:
            continue

        power_rating = safe_float(
            record.get(
                "power_rating"
            )
        )

        if power_rating is None:
            continue

        lookup[
            team
        ] = record

    return lookup


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
    """Return whether game occurs before Sept. 1 UTC."""

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
# CALIBRATION LOADERS
# ============================================================

def load_margin_calibration():
    """Load V3 margin calibration."""

    data = load_json(
        MARGIN_CALIBRATION_FILE
    )

    model = data.get(
        "model"
    )

    if not isinstance(
        model,
        dict
    ):
        raise ValueError(
            "Margin calibration file is missing model object."
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
            "Margin rating-gap coefficient is missing."
        )

    if home_field_advantage is None:
        raise ValueError(
            "Margin home-field coefficient is missing."
        )

    return {
        "model_version":
            data.get(
                "model_version",
                "game_margin_calibration_v3",
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


def load_total_calibration():
    """Load game-total calibration."""

    data = load_json(
        TOTAL_CALIBRATION_FILE
    )

    model = data.get(
        "model"
    )

    if not isinstance(
        model,
        dict
    ):
        raise ValueError(
            "Total calibration file is missing model object."
        )

    required = [
        "intercept",
        "home_offense_coefficient",
        "away_offense_coefficient",
        "home_defense_coefficient",
        "away_defense_coefficient",
    ]

    output = {
        "model_version":
            data.get(
                "model_version",
                "game_total_calibration_v1",
            ),

        "games_tested":
            data.get(
                "games_tested"
            ),
    }

    for key in required:

        value = safe_float(
            model.get(
                key
            )
        )

        if value is None:
            raise ValueError(
                f"Total calibration field missing: {key}"
            )

        output[
            key
        ] = value

    return output


# ============================================================
# MARGIN MODEL
# ============================================================

def calculate_projected_home_margin(
    home_rating,
    away_rating,
    neutral_site,
    calibration,
):
    """Calculate calibrated home margin."""

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

        "home_field_component":
            home_field_margin,

        "projected_home_margin":
            projected_home_margin,
    }


# ============================================================
# TOTAL MODEL
# ============================================================

def calculate_projected_total(
    home_record,
    away_record,
    calibration,
):
    """Calculate calibrated projected total."""

    home_offense = safe_float(
        home_record.get(
            "offense_score"
        )
    )

    away_offense = safe_float(
        away_record.get(
            "offense_score"
        )
    )

    home_defense = safe_float(
        home_record.get(
            "defense_score"
        )
    )

    away_defense = safe_float(
        away_record.get(
            "defense_score"
        )
    )

    if (
        home_offense is None
        or
        away_offense is None
        or
        home_defense is None
        or
        away_defense is None
    ):
        return None

    projected_total = (
        calibration[
            "intercept"
        ]
        +
        calibration[
            "home_offense_coefficient"
        ]
        *
        home_offense
        +
        calibration[
            "away_offense_coefficient"
        ]
        *
        away_offense
        +
        calibration[
            "home_defense_coefficient"
        ]
        *
        home_defense
        +
        calibration[
            "away_defense_coefficient"
        ]
        *
        away_defense
    )

    return {
        "home_offense":
            home_offense,

        "away_offense":
            away_offense,

        "home_defense":
            home_defense,

        "away_defense":
            away_defense,

        "projected_total":
            projected_total,
    }


# ============================================================
# IMPLIED SCORES
# ============================================================

def calculate_implied_scores(
    projected_total,
    projected_home_margin,
):
    """Calculate implied scores from total and margin."""

    projected_home_score = (
        projected_total
        +
        projected_home_margin
    ) / 2.0

    projected_away_score = (
        projected_total
        -
        projected_home_margin
    ) / 2.0

    return {
        "projected_home_score":
            projected_home_score,

        "projected_away_score":
            projected_away_score,
    }


# ============================================================
# GAME PROJECTION
# ============================================================

def project_game(
    game,
    rating_lookup,
    margin_calibration,
    total_calibration,
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

    margin_components = (
        calculate_projected_home_margin(
            home_rating,
            away_rating,
            neutral_site,
            margin_calibration,
        )
    )

    total_components = (
        calculate_projected_total(
            home_record,
            away_record,
            total_calibration,
        )
    )

    if total_components is None:
        return None

    projected_home_margin = (
        margin_components[
            "projected_home_margin"
        ]
    )

    projected_total = (
        total_components[
            "projected_total"
        ]
    )

    implied_scores = (
        calculate_implied_scores(
            projected_total,
            projected_home_margin,
        )
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
                margin_components[
                    "rating_gap"
                ],
                4,
            ),

        "rating_margin_component":
            round(
                margin_components[
                    "rating_margin"
                ],
                4,
            ),

        "home_field_component":
            round(
                margin_components[
                    "home_field_component"
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

        "projected_total":
            round(
                projected_total,
                2,
            ),

        "projected_home_score":
            round(
                implied_scores[
                    "projected_home_score"
                ],
                2,
            ),

        "projected_away_score":
            round(
                implied_scores[
                    "projected_away_score"
                ],
                2,
            ),

        "home_offense_score":
            round(
                total_components[
                    "home_offense"
                ],
                4,
            ),

        "away_offense_score":
            round(
                total_components[
                    "away_offense"
                ],
                4,
            ),

        "home_defense_score":
            round(
                total_components[
                    "home_defense"
                ],
                4,
            ),

        "away_defense_score":
            round(
                total_components[
                    "away_defense"
                ],
                4,
            ),

        "rating_model":
            home_record.get(
                "model_version",
                "2026_preseason_provisional_v1",
            ),

        "margin_calibration_model":
            margin_calibration[
                "model_version"
            ],

        "total_calibration_model":
            total_calibration[
                "model_version"
            ],

        "provisional":
            True,
    }


# ============================================================
# BUILD PREDICTIONS
# ============================================================

def build_predictions():
    """Generate calibrated provisional spread + total predictions."""

    required_files = [
        RATINGS_FILE,
        GAMES_FILE,
        MARGIN_CALIBRATION_FILE,
        TOTAL_CALIBRATION_FILE,
    ]

    for path in required_files:

        if not path.exists():

            raise FileNotFoundError(
                f"Missing required file: {path}"
            )

    ratings = load_json(
        RATINGS_FILE
    )

    games = load_json(
        GAMES_FILE
    )

    margin_calibration = (
        load_margin_calibration()
    )

    total_calibration = (
        load_total_calibration()
    )

    rating_lookup = build_rating_lookup(
        ratings
    )

    predictions = []

    skipped_non_fbs = 0
    skipped_missing_data = 0

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
            margin_calibration,
            total_calibration,
        )

        if projection is None:

            skipped_missing_data += 1
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
        "PROJECT GRIDIRON 2026 PROVISIONAL SPREAD + TOTAL PREDICTIONS"
    )

    print("=" * 80)

    print()

    print(
        "MARGIN CALIBRATION"
    )

    print("-" * 80)

    print(
        f"Rating coefficient: "
        f"{margin_calibration['rating_gap_coefficient']:.4f}"
    )

    print(
        f"Home-field advantage: "
        f"{margin_calibration['home_field_advantage']:.4f}"
    )

    print()

    print(
        "TOTAL CALIBRATION"
    )

    print("-" * 80)

    print(
        f"Intercept: "
        f"{total_calibration['intercept']:.4f}"
    )

    print(
        f"Home offense: "
        f"{total_calibration['home_offense_coefficient']:+.4f}"
    )

    print(
        f"Away offense: "
        f"{total_calibration['away_offense_coefficient']:+.4f}"
    )

    print(
        f"Home defense: "
        f"{total_calibration['home_defense_coefficient']:+.4f}"
    )

    print(
        f"Away defense: "
        f"{total_calibration['away_defense_coefficient']:+.4f}"
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
        f"Eligible games: "
        f"{eligible_games}"
    )

    print(
        f"Predictions generated: "
        f"{len(predictions)}"
    )

    print(
        f"Non-FBS games skipped: "
        f"{skipped_non_fbs}"
    )

    print(
        f"Games skipped for missing data: "
        f"{skipped_missing_data}"
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
            f"  spread: "
            f"{winner} "
            f"by "
            f"{record['projected_margin']:.1f}"
        )

        print(
            f"  total: "
            f"{record['projected_total']:.1f}"
        )

        print(
            f"  projected score: "
            f"{record['away_team']} "
            f"{record['projected_away_score']:.1f}, "
            f"{record['home_team']} "
            f"{record['projected_home_score']:.1f}"
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
