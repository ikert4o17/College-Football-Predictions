"""
Project Gridiron
2026 Provisional Preseason Ratings V2

Purpose
-------
Generate a usable 2026 preseason power-rating set before the full
Project Gridiron V4 preseason inputs are available.

Current provisional model:

    2025 Project Gridiron power rating
        +
    2026 returning-snaps adjustment
        =
    2026 provisional preseason power rating

For totals modeling, this version also carries forward:

    2025 offense_score
    2025 defense_score

with the same conservative regression toward the FBS mean.

Important
---------
Returning snaps currently adjust ONLY the overall power rating.

They do not directly alter offense_score or defense_score because we have
not yet validated how returning continuity should be split between offense
and defense.

Inputs
------
data/processed/power_ratings_2025.json
data/raw/returning_production/2026.json
data/processed/teams.json

Output
------
data/processed/power_ratings_2026.json

Usage
-----
python -m ratings.preseason_rating_2026
"""

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# FILES
# ============================================================

POWER_RATINGS_2025_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "power_ratings_2025.json"
)

RETURNING_SNAPS_2026_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "returning_production"
    / "2026.json"
)

TEAMS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "teams.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "power_ratings_2026.json"
)


# ============================================================
# MODEL SETTINGS
# ============================================================

RETURNING_SNAPS_WEIGHT = 1.25

MAX_RETURNING_ADJUSTMENT = 3.0

REGRESSION_TO_MEAN = 0.10


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
    default=0.0
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


def mean(values):
    """Arithmetic mean."""

    if not values:
        return 0.0

    return (
        sum(values)
        /
        len(values)
    )


def standard_deviation(values):
    """Population standard deviation."""

    if not values:
        return 0.0

    average = mean(
        values
    )

    variance = (
        sum(
            (
                value
                -
                average
            )
            ** 2
            for value in values
        )
        /
        len(values)
    )

    return math.sqrt(
        variance
    )


def z_score(
    value,
    average,
    std
):
    """Convert value to z-score."""

    if std == 0:
        return 0.0

    return (
        value
        -
        average
    ) / std


def regress_to_mean(
    value,
    average
):
    """Regress prior-season value toward FBS mean."""

    return (
        value
        *
        (
            1.0
            -
            REGRESSION_TO_MEAN
        )
        +
        average
        *
        REGRESSION_TO_MEAN
    )


def build_lookup(
    records,
    team_key="team"
):
    """Build lookup keyed by team."""

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
            team_key
        )

        if team:
            lookup[
                team
            ] = record

    return lookup


def build_team_metadata_lookup(records):
    """Build team metadata lookup."""

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

        name = record.get(
            "name"
        )

        if not name:
            continue

        lookup[
            name
        ] = record

    return lookup


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_inputs():
    """Verify required files exist."""

    required = {
        "2025 power ratings":
            POWER_RATINGS_2025_FILE,

        "2026 returning snaps":
            RETURNING_SNAPS_2026_FILE,

        "team metadata":
            TEAMS_FILE,
    }

    missing = []

    print("=" * 78)
    print("PROJECT GRIDIRON 2026 PROVISIONAL INPUT CHECK")
    print("=" * 78)
    print()

    for name, path in required.items():

        if path.exists():

            print(
                f"FOUND:   "
                f"{name}"
            )

            print(
                f"         "
                f"{path}"
            )

        else:

            print(
                f"MISSING: "
                f"{name}"
            )

            print(
                f"         "
                f"{path}"
            )

            missing.append(
                path
            )

    print()

    if missing:

        raise FileNotFoundError(
            "One or more provisional 2026 rating inputs are missing."
        )


# ============================================================
# RETURNING-SNAPS CONTEXT
# ============================================================

def calculate_returning_context(
    returning_lookup
):
    """Calculate returning-snap percentage distribution."""

    values = []

    for record in returning_lookup.values():

        percent = safe_float(
            record.get(
                "returning_snap_percent"
            ),
            default=None,
        )

        if percent is None:
            continue

        values.append(
            percent
        )

    return {
        "mean":
            mean(
                values
            ),

        "std":
            standard_deviation(
                values
            ),

        "min":
            min(
                values
            )
            if values
            else 0.0,

        "max":
            max(
                values
            )
            if values
            else 0.0,

        "count":
            len(
                values
            ),
    }


def calculate_returning_adjustment(
    returning_percent,
    context
):
    """Calculate returning-snaps adjustment."""

    standardized = z_score(
        returning_percent,
        context[
            "mean"
        ],
        context[
            "std"
        ],
    )

    adjustment = (
        standardized
        *
        RETURNING_SNAPS_WEIGHT
    )

    adjustment = max(
        -MAX_RETURNING_ADJUSTMENT,
        min(
            adjustment,
            MAX_RETURNING_ADJUSTMENT,
        ),
    )

    return adjustment


# ============================================================
# BUILD RATINGS
# ============================================================

def build_provisional_ratings():
    """Generate 2026 provisional ratings."""

    validate_inputs()

    prior_records = load_json(
        POWER_RATINGS_2025_FILE
    )

    returning_records = load_json(
        RETURNING_SNAPS_2026_FILE
    )

    team_records = load_json(
        TEAMS_FILE
    )

    prior_lookup = build_lookup(
        prior_records
    )

    returning_lookup = build_lookup(
        returning_records
    )

    metadata_lookup = build_team_metadata_lookup(
        team_records
    )

    # --------------------------------------------------------
    # PRIOR-YEAR CONTEXT
    # --------------------------------------------------------

    prior_power_values = [
        safe_float(
            record.get(
                "power_rating"
            )
        )
        for record in prior_lookup.values()
    ]

    prior_offense_values = [
        safe_float(
            record.get(
                "offense_score"
            )
        )
        for record in prior_lookup.values()
    ]

    prior_defense_values = [
        safe_float(
            record.get(
                "defense_score"
            )
        )
        for record in prior_lookup.values()
    ]

    prior_power_mean = mean(
        prior_power_values
    )

    prior_offense_mean = mean(
        prior_offense_values
    )

    prior_defense_mean = mean(
        prior_defense_values
    )

    returning_context = (
        calculate_returning_context(
            returning_lookup
        )
    )

    print("=" * 78)
    print("PROJECT GRIDIRON 2026 PROVISIONAL PRESEASON RATINGS V2")
    print("=" * 78)
    print()

    print(
        f"2025 rated teams: "
        f"{len(prior_lookup)}"
    )

    print(
        f"2026 returning-snap teams: "
        f"{len(returning_lookup)}"
    )

    print(
        f"2026 FBS teams: "
        f"{len(metadata_lookup)}"
    )

    print()

    print(
        "2025 COMPONENT MEANS"
    )

    print("-" * 78)

    print(
        f"Power rating mean: "
        f"{prior_power_mean:.2f}"
    )

    print(
        f"Offense score mean: "
        f"{prior_offense_mean:.2f}"
    )

    print(
        f"Defense score mean: "
        f"{prior_defense_mean:.2f}"
    )

    print()

    print(
        "RETURNING-SNAPS CONTEXT"
    )

    print("-" * 78)

    print(
        f"Teams: "
        f"{returning_context['count']}"
    )

    print(
        f"Mean returning snaps %: "
        f"{returning_context['mean']:.2f}"
    )

    print(
        f"Std dev: "
        f"{returning_context['std']:.2f}"
    )

    print(
        f"Min: "
        f"{returning_context['min']:.2f}"
    )

    print(
        f"Max: "
        f"{returning_context['max']:.2f}"
    )

    print()

    ratings = []

    unmatched_prior = []

    for team_name in sorted(
        metadata_lookup
    ):

        prior = prior_lookup.get(
            team_name
        )

        returning = returning_lookup.get(
            team_name
        )

        # ----------------------------------------------------
        # PRIOR-YEAR BASELINE
        # ----------------------------------------------------

        if prior:

            prior_power_rating = safe_float(
                prior.get(
                    "power_rating"
                ),
                prior_power_mean,
            )

            prior_offense_score = safe_float(
                prior.get(
                    "offense_score"
                ),
                prior_offense_mean,
            )

            prior_defense_score = safe_float(
                prior.get(
                    "defense_score"
                ),
                prior_defense_mean,
            )

            prior_rank = prior.get(
                "rank"
            )

        else:

            prior_power_rating = (
                prior_power_mean
            )

            prior_offense_score = (
                prior_offense_mean
            )

            prior_defense_score = (
                prior_defense_mean
            )

            prior_rank = None

            unmatched_prior.append(
                team_name
            )

        # ----------------------------------------------------
        # REGRESSION
        # ----------------------------------------------------

        regressed_power_rating = (
            regress_to_mean(
                prior_power_rating,
                prior_power_mean,
            )
        )

        regressed_offense_score = (
            regress_to_mean(
                prior_offense_score,
                prior_offense_mean,
            )
        )

        regressed_defense_score = (
            regress_to_mean(
                prior_defense_score,
                prior_defense_mean,
            )
        )

        # ----------------------------------------------------
        # RETURNING SNAPS
        # ----------------------------------------------------

        if returning:

            returning_percent = safe_float(
                returning.get(
                    "returning_snap_percent"
                ),
                returning_context[
                    "mean"
                ],
            )

            returning_rank = returning.get(
                "rank_by_returning_snaps"
            )

            returning_snaps = returning.get(
                "returning_snaps"
            )

            returning_adjustment = (
                calculate_returning_adjustment(
                    returning_percent,
                    returning_context,
                )
            )

        else:

            returning_percent = (
                returning_context[
                    "mean"
                ]
            )

            returning_rank = None

            returning_snaps = None

            returning_adjustment = 0.0

        provisional_power_rating = (
            regressed_power_rating
            +
            returning_adjustment
        )

        metadata = metadata_lookup.get(
            team_name,
            {},
        )

        ratings.append(
            {
                "season":
                    2026,

                "team":
                    team_name,

                "conference":
                    metadata.get(
                        "conference"
                    ),

                "provisional":
                    True,

                "model_version":
                    "2026_preseason_provisional_v2",

                "prior_2025_power_rating":
                    round(
                        prior_power_rating,
                        4,
                    ),

                "prior_2025_offense_score":
                    round(
                        prior_offense_score,
                        4,
                    ),

                "prior_2025_defense_score":
                    round(
                        prior_defense_score,
                        4,
                    ),

                "prior_2025_rank":
                    prior_rank,

                "regressed_baseline":
                    round(
                        regressed_power_rating,
                        4,
                    ),

                "offense_score":
                    round(
                        regressed_offense_score,
                        4,
                    ),

                "defense_score":
                    round(
                        regressed_defense_score,
                        4,
                    ),

                "returning_snap_percent":
                    returning_percent,

                "returning_snaps":
                    returning_snaps,

                "returning_snap_rank":
                    returning_rank,

                "returning_adjustment":
                    round(
                        returning_adjustment,
                        4,
                    ),

                "power_rating":
                    round(
                        provisional_power_rating,
                        4,
                    ),
            }
        )

    # --------------------------------------------------------
    # RANK
    # --------------------------------------------------------

    ratings.sort(
        key=lambda record:
            record[
                "power_rating"
            ],
        reverse=True,
    )

    for rank, record in enumerate(
        ratings,
        start=1,
    ):

        record[
            "rank"
        ] = rank

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            ratings,
            file,
            indent=4,
        )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    print(
        "MODEL SETTINGS"
    )

    print("-" * 78)

    print(
        f"Regression to mean: "
        f"{REGRESSION_TO_MEAN:.2%}"
    )

    print(
        f"Returning-snaps weight: "
        f"{RETURNING_SNAPS_WEIGHT:.2f} pts/std"
    )

    print(
        f"Maximum returning adjustment: "
        f"{MAX_RETURNING_ADJUSTMENT:.2f}"
    )

    print()

    print(
        "TOP 25 2026 PROVISIONAL RATINGS"
    )

    print("-" * 78)

    for record in ratings[:25]:

        print(
            f"{record['rank']:>3}. "
            f"{record['team']:<24} "
            f"PR={record['power_rating']:>7.2f}  "
            f"OFF={record['offense_score']:>6.2f}  "
            f"DEF={record['defense_score']:>6.2f}  "
            f"ret={record['returning_snap_percent']:>5.1f}%"
        )

    if unmatched_prior:

        print()

        print(
            "TEAMS WITHOUT 2025 PROJECT GRIDIRON RATING"
        )

        print("-" * 78)

        for team in unmatched_prior:

            print(
                team
            )

    print()

    print(
        f"Ratings generated: "
        f"{len(ratings)}"
    )

    print(
        "Saved to:"
    )

    print(
        OUTPUT_FILE
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "These are provisional Week 0 preseason ratings."
    )

    print(
        "Overall power includes returning-snaps adjustment."
    )

    print(
        "Offense/defense components are regressed 2025 values only."
    )

    print(
        "They are not final V4 ratings."
    )

    return ratings


if __name__ == "__main__":

    build_provisional_ratings()
