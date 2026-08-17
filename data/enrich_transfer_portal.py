"""
Enrich transfer portal records with historical recruiting ratings.

Primary talent measure:
    CFBD transfer portal rating

Fallback talent measure:
    Original CFBD recruiting rating

Usage:
    python -m data.enrich_transfer_portal 2025
    python -m data.enrich_transfer_portal 2026

The module searches recruiting classes from 2019 through the
specified transfer season.

This module does NOT modify the power-rating model.
It creates an enriched transfer dataset for later analysis.
"""

import json
import re
import sys
import unicodedata
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RECRUITING_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "recruiting_players"
)


def transfer_file(year):
    """Return raw transfer portal file for a season."""

    return (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "transfer_portal"
        / f"{year}.json"
    )


def output_file(year):
    """Return enriched transfer portal output file."""

    return (
        PROJECT_ROOT
        / "data"
        / "processed"
        / f"enriched_transfer_portal_{year}.json"
    )


def load_json(path):
    """Load JSON data."""

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def normalize_text(value):
    """Normalize text for conservative player matching."""

    if not value:
        return ""

    value = unicodedata.normalize(
        "NFKD",
        str(value)
    )

    value = "".join(
        character
        for character in value
        if not unicodedata.combining(
            character
        )
    )

    value = value.lower()

    value = value.replace(
        "&",
        "and"
    )

    value = re.sub(
        r"[^a-z0-9\s]",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    ).strip()

    parts = value.split()

    suffixes = {
        "jr",
        "sr",
        "ii",
        "iii",
        "iv",
        "v",
    }

    while (
        parts
        and parts[-1] in suffixes
    ):
        parts.pop()

    return " ".join(parts)


def safe_float(value):
    """Convert a value safely to float."""

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return None


def portal_player_name(record):
    """Build a transfer player's full name."""

    first_name = (
        record.get(
            "firstName"
        )
        or ""
    )

    last_name = (
        record.get(
            "lastName"
        )
        or ""
    )

    return (
        f"{first_name} {last_name}"
    ).strip()


def load_recruiting_records(year):
    """
    Load historical recruiting classes through the transfer season.

    Example:
        2025 portal -> recruiting classes 2019-2025
        2026 portal -> recruiting classes 2019-2026
    """

    records = []

    loaded_years = []

    for recruiting_year in range(
        2019,
        year + 1
    ):

        path = (
            RECRUITING_DIRECTORY
            / f"{recruiting_year}.json"
        )

        if not path.exists():
            continue

        year_records = load_json(
            path
        )

        records.extend(
            year_records
        )

        loaded_years.append(
            recruiting_year
        )

    return (
        records,
        loaded_years,
    )


def build_recruiting_index(
    recruiting_records
):
    """Index recruiting records by normalized player name."""

    index = {}

    for record in recruiting_records:

        name = normalize_text(
            record.get(
                "name"
            )
        )

        if not name:
            continue

        index.setdefault(
            name,
            []
        ).append(
            record
        )

    return index


def candidate_score(
    transfer,
    recruit
):
    """
    Score one recruiting candidate.

    Origin school match is strongest.
    Position match is secondary.

    Fuzzy-name matching is intentionally not used.
    """

    score = 0

    origin = normalize_text(
        transfer.get(
            "origin"
        )
    )

    committed_to = normalize_text(
        recruit.get(
            "committedTo"
        )
    )

    if (
        origin
        and committed_to
        and origin == committed_to
    ):
        score += 6

    transfer_position = normalize_text(
        transfer.get(
            "position"
        )
    )

    recruit_position = normalize_text(
        recruit.get(
            "position"
        )
    )

    if (
        transfer_position
        and recruit_position
        and transfer_position
        == recruit_position
    ):
        score += 3

    return score


def find_recruiting_match(
    transfer,
    recruiting_index
):
    """Find a conservative historical recruiting match."""

    name = normalize_text(
        portal_player_name(
            transfer
        )
    )

    candidates = recruiting_index.get(
        name,
        []
    )

    if not candidates:
        return (
            None,
            "unmatched"
        )

    if len(candidates) == 1:

        return (
            candidates[0],
            "unique_name"
        )

    scored = []

    for candidate in candidates:

        score = candidate_score(
            transfer,
            candidate
        )

        scored.append(
            (
                score,
                candidate,
            )
        )

    scored.sort(
        key=lambda item:
            item[0],
        reverse=True,
    )

    highest_score = scored[0][0]

    highest_candidates = [
        candidate
        for score, candidate in scored
        if score == highest_score
    ]

    if (
        highest_score >= 3
        and len(highest_candidates) == 1
    ):

        return (
            highest_candidates[0],
            "scored_match"
        )

    return (
        None,
        "ambiguous"
    )


def enrich_transfer(
    transfer,
    recruiting_index
):
    """Add recruiting and effective talent ratings."""

    recruiting_match, match_method = (
        find_recruiting_match(
            transfer,
            recruiting_index
        )
    )

    portal_rating = safe_float(
        transfer.get(
            "rating"
        )
    )

    portal_stars = transfer.get(
        "stars"
    )

    recruiting_rating = None
    recruiting_stars = None
    recruiting_year = None
    recruiting_school = None
    recruiting_type = None
    recruiting_id = None
    recruiting_athlete_id = None

    if recruiting_match:

        recruiting_rating = safe_float(
            recruiting_match.get(
                "rating"
            )
        )

        recruiting_stars = (
            recruiting_match.get(
                "stars"
            )
        )

        recruiting_year = (
            recruiting_match.get(
                "year"
            )
        )

        recruiting_school = (
            recruiting_match.get(
                "committedTo"
            )
        )

        recruiting_type = (
            recruiting_match.get(
                "recruitType"
            )
        )

        recruiting_id = (
            recruiting_match.get(
                "id"
            )
        )

        recruiting_athlete_id = (
            recruiting_match.get(
                "athleteId"
            )
        )

    # Portal rating represents the player at transfer time
    # and remains our preferred talent measure.
    if portal_rating is not None:

        effective_rating = (
            portal_rating
        )

        effective_rating_source = (
            "portal"
        )

    elif recruiting_rating is not None:

        effective_rating = (
            recruiting_rating
        )

        effective_rating_source = (
            "recruiting_fallback"
        )

    else:

        effective_rating = None

        effective_rating_source = (
            "unrated"
        )

    enriched = dict(
        transfer
    )

    enriched[
        "player"
    ] = portal_player_name(
        transfer
    )

    enriched[
        "recruiting_match"
    ] = {
        "matched":
            recruiting_match
            is not None,

        "method":
            match_method,

        "recruiting_id":
            recruiting_id,

        "athlete_id":
            recruiting_athlete_id,

        "year":
            recruiting_year,

        "committed_to":
            recruiting_school,

        "recruit_type":
            recruiting_type,

        "rating":
            recruiting_rating,

        "stars":
            recruiting_stars,
    }

    enriched[
        "talent"
    ] = {
        "portal_rating":
            portal_rating,

        "portal_stars":
            portal_stars,

        "recruiting_rating":
            recruiting_rating,

        "recruiting_stars":
            recruiting_stars,

        "effective_rating":
            effective_rating,

        "effective_rating_source":
            effective_rating_source,
    }

    return enriched


def enrich_transfer_portal(year):
    """Enrich all portal records for one season."""

    source = transfer_file(
        year
    )

    destination = output_file(
        year
    )

    if not source.exists():

        raise FileNotFoundError(
            f"Transfer portal file not found: "
            f"{source}"
        )

    transfers = load_json(
        source
    )

    (
        recruiting_records,
        loaded_years,
    ) = load_recruiting_records(
        year
    )

    if not recruiting_records:

        raise FileNotFoundError(
            "No recruiting history files were available "
            f"for transfer season {year}."
        )

    recruiting_index = (
        build_recruiting_index(
            recruiting_records
        )
    )

    enriched_records = []

    for transfer in transfers:

        enriched_records.append(
            enrich_transfer(
                transfer,
                recruiting_index
            )
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with destination.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            enriched_records,
            file,
            indent=4
        )

    total = len(
        enriched_records
    )

    direct_portal_ratings = sum(
        1
        for record in enriched_records
        if record[
            "talent"
        ][
            "portal_rating"
        ] is not None
    )

    recruiting_matches = sum(
        1
        for record in enriched_records
        if record[
            "recruiting_match"
        ][
            "matched"
        ]
    )

    recruiting_fallbacks = sum(
        1
        for record in enriched_records
        if record[
            "talent"
        ][
            "effective_rating_source"
        ]
        == "recruiting_fallback"
    )

    effective_ratings = sum(
        1
        for record in enriched_records
        if record[
            "talent"
        ][
            "effective_rating"
        ] is not None
    )

    ambiguous = sum(
        1
        for record in enriched_records
        if record[
            "recruiting_match"
        ][
            "method"
        ]
        == "ambiguous"
    )

    unmatched = sum(
        1
        for record in enriched_records
        if record[
            "recruiting_match"
        ][
            "method"
        ]
        == "unmatched"
    )

    print("=" * 70)

    print(
        f"{year} TRANSFER PORTAL TALENT ENRICHMENT"
    )

    print("=" * 70)

    print(
        f"Transfer records: "
        f"{total}"
    )

    print(
        "Recruiting classes loaded: "
        + ", ".join(
            str(value)
            for value in loaded_years
        )
    )

    print(
        f"Historical recruiting records: "
        f"{len(recruiting_records)}"
    )

    print()

    print(
        f"Direct portal ratings: "
        f"{direct_portal_ratings}"
    )

    print(
        f"Recruiting-history matches: "
        f"{recruiting_matches}"
    )

    print(
        f"Recruiting rating fallbacks used: "
        f"{recruiting_fallbacks}"
    )

    print(
        f"Transfers with effective talent rating: "
        f"{effective_ratings}"
    )

    if total > 0:

        print(
            f"Effective rating coverage: "
            f"{effective_ratings / total * 100:.1f}%"
        )

    print(
        f"Ambiguous recruiting matches: "
        f"{ambiguous}"
    )

    print(
        f"Unmatched recruiting players: "
        f"{unmatched}"
    )

    print()

    source_counts = {}

    for record in enriched_records:

        source_name = record[
            "talent"
        ][
            "effective_rating_source"
        ]

        source_counts[
            source_name
        ] = (
            source_counts.get(
                source_name,
                0
            )
            + 1
        )

    print(
        "EFFECTIVE RATING SOURCES"
    )

    print("-" * 70)

    for (
        source_name,
        count
    ) in sorted(
        source_counts.items()
    ):

        print(
            f"{source_name}: "
            f"{count}"
        )

    print()

    rated_records = [
        record
        for record in enriched_records
        if record[
            "talent"
        ][
            "effective_rating"
        ] is not None
    ]

    rated_records.sort(
        key=lambda record:
            record[
                "talent"
            ][
                "effective_rating"
            ],
        reverse=True,
    )

    print(
        "TOP 15 TRANSFERS BY EFFECTIVE RATING"
    )

    print("-" * 70)

    for record in rated_records[:15]:

        talent = record[
            "talent"
        ]

        print(
            f"{record['player']}: "
            f"{record.get('origin')} -> "
            f"{record.get('destination')}, "
            f"rating="
            f"{talent['effective_rating']:.4f}, "
            f"source="
            f"{talent['effective_rating_source']}"
        )

    print()

    print(
        f"Saved to {destination}"
    )


if __name__ == "__main__":

    year = 2025

    if len(sys.argv) > 1:

        year = int(
            sys.argv[1]
        )

    enrich_transfer_portal(
        year
    )
