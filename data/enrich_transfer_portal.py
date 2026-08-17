"""
Enrich 2025 transfer portal records with historical recruiting ratings.

Primary talent measure:
    CFBD transfer portal rating

Fallback talent measure:
    Original CFBD recruiting rating

The recruiting history covers 2019 through 2025.

This module does NOT modify the power-rating model.
It creates an enriched transfer dataset for later analysis.
"""

import json
import re
import unicodedata
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

TRANSFER_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "transfer_portal"
    / "2025.json"
)

RECRUITING_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "recruiting_players"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "enriched_transfer_portal_2025.json"
)


RECRUITING_YEARS = range(
    2019,
    2026,
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

    # Remove common suffixes.
    parts = value.split()

    suffixes = {
        "jr",
        "sr",
        "ii",
        "iii",
        "iv",
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
    """Build the full player name from a portal record."""

    first_name = record.get(
        "firstName",
        ""
    )

    last_name = record.get(
        "lastName",
        ""
    )

    return (
        f"{first_name} {last_name}"
    ).strip()


def load_recruiting_records():
    """Load all historical recruiting classes."""

    records = []

    for year in RECRUITING_YEARS:

        path = (
            RECRUITING_DIRECTORY
            / f"{year}.json"
        )

        if not path.exists():
            continue

        year_records = load_json(
            path
        )

        records.extend(
            year_records
        )

    return records


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
    Score a recruiting candidate for a transfer.

    School match is strongest.
    Position match is also useful.

    We intentionally avoid fuzzy-name matching here.
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
    """Find a conservative recruiting match."""

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
        return None, "unmatched"

    # An exact normalized name with only one recruiting
    # record is safe enough for our initial analysis.
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

    # For duplicated names, require supporting
    # position/school information and a unique winner.
    if (
        highest_score >= 3
        and len(highest_candidates) == 1
    ):
        return (
            highest_candidates[0],
            "scored_match"
        )

    return None, "ambiguous"


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

    # Portal rating is preferred because it represents
    # the player at transfer time.
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


def enrich_transfer_portal():
    """Enrich all transfer portal records."""

    transfers = load_json(
        TRANSFER_FILE
    )

    recruiting_records = (
        load_recruiting_records()
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

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
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

    print("=" * 60)
    print(
        "TRANSFER PORTAL TALENT ENRICHMENT"
    )
    print("=" * 60)

    print(
        f"Transfer records: "
        f"{total}"
    )

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

        source = record[
            "talent"
        ][
            "effective_rating_source"
        ]

        source_counts[source] = (
            source_counts.get(
                source,
                0
            )
            + 1
        )

    print(
        "EFFECTIVE RATING SOURCES"
    )
    print("-" * 60)

    for (
        source,
        count
    ) in sorted(
        source_counts.items()
    ):

        print(
            f"{source}: {count}"
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
    print("-" * 60)

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
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    enrich_transfer_portal()
