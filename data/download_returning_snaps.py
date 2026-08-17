"""
Download returning snap data from Punt & Rally.

Punt & Rally provides team-level returning production data,
including returning snaps and snapback percentage.

For a target season, the returning snap data describes
the players returning from the previous season.

This module downloads:
    - Returning snaps
    - Snapback percentage

The data is saved in raw JSON format for later processing.
"""

import json
import re
import sys
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "returning_snaps"
)

BASE_URL = (
    "https://www.puntandrally.com/"
    "viewreturnprod.php"
)


def clean_team_name(team_name):
    """Clean a team name extracted from the webpage."""

    if not team_name:
        return None

    team_name = re.sub(
        r"\s+",
        " ",
        team_name
    ).strip()

    return team_name


def parse_number(value):
    """Convert a numeric string into int or float."""

    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    value = value.replace(
        ",",
        ""
    )

    try:
        if "." in value:
            return float(value)

        return int(value)

    except ValueError:
        return None


def parse_percent(value):
    """Convert a percentage string into a decimal."""

    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    value = value.replace(
        "%",
        ""
    )

    try:
        return float(value) / 100.0

    except ValueError:
        return None


def download_page(year):
    """Download the Punt & Rally returning-snaps page."""

    params = {
        "whichyear": year,
        "stat": "overall",
        "showportal": "N",
        "sortby": "snaps",
    }

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; "
                "College-Football-Predictions/1.0)"
            )
        },
    )

    response.raise_for_status()

    return response.text


def extract_rows(html):
    """
    Extract team returning-snap rows from the HTML.

    Punt & Rally presents the data in an HTML table.
    We use the table structure rather than relying on
    a fixed line number or page layout.
    """

    rows = re.findall(
        r"<tr[^>]*>(.*?)</tr>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    records = []

    for row in rows:

        cells = re.findall(
            r"<t[dh][^>]*>(.*?)</t[dh]>",
            row,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if len(cells) < 2:
            continue

        cleaned_cells = []

        for cell in cells:

            cell = re.sub(
                r"<[^>]+>",
                " ",
                cell,
            )

            cell = (
                cell
                .replace(
                    "&nbsp;",
                    " ",
                )
                .replace(
                    "&amp;",
                    "&",
                )
            )

            cell = re.sub(
                r"\s+",
                " ",
                cell,
            ).strip()

            cleaned_cells.append(cell)

        if not cleaned_cells:
            continue

        team = clean_team_name(
            cleaned_cells[0]
        )

        if not team:
            continue

        lower_team = team.lower()

        # Skip headers and non-team rows.
        if lower_team in {
            "team",
            "school",
            "total",
            "totals",
        }:
            continue

        # Find numeric values in the row.
        numeric_values = []

        for cell in cleaned_cells[1:]:

            number = parse_number(cell)

            if number is not None:
                numeric_values.append(
                    number
                )

        if not numeric_values:
            continue

        # Returning snaps are the first large integer
        # value in the table row.
        returning_snaps = None

        for number in numeric_values:

            if (
                isinstance(number, int)
                and number >= 0
            ):
                returning_snaps = number
                break

        if returning_snaps is None:
            continue

        # Find a percentage in the original row.
        percentages = re.findall(
            r"(\d+(?:\.\d+)?)\s*%",
            row,
            flags=re.IGNORECASE,
        )

        snapback_percent = None

        if percentages:

            snapback_percent = (
                float(percentages[0])
                / 100.0
            )

        records.append(
            {
                "team": team,
                "returning_snaps": returning_snaps,
                "snapback_percent": snapback_percent,
            }
        )

    return records


def download_returning_snaps(year):
    """Download and save returning snap data."""

    print("=" * 60)
    print(
        "PUNT & RALLY RETURNING SNAPS"
    )
    print("=" * 60)

    print(
        f"Downloading returning snaps for {year}..."
    )

    html = download_page(
        year
    )

    print(
        f"Downloaded page: "
        f"{len(html):,} characters"
    )

    records = extract_rows(
        html
    )

    if not records:
        raise RuntimeError(
            "No returning snap records were "
            "found on the Punt & Rally page."
        )

    # Remove duplicate team records while preserving
    # the first valid record.
    unique_records = {}

    for record in records:

        team = record["team"]

        if team not in unique_records:
            unique_records[team] = record

    records = list(
        unique_records.values()
    )

    records.sort(
        key=lambda record:
            record["team"]
    )

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        OUTPUT_DIRECTORY
        / f"{year}.json"
    )

    output = {
        "source": "Punt & Rally",
        "source_url": BASE_URL,
        "season": year,
        "stat": "overall",
        "records": records,
    }

    with output_file.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            output,
            file,
            indent=4
        )

    print()
    print(
        f"Teams found: "
        f"{len(records)}"
    )

    print(
        f"Saved to {output_file}"
    )

    print()

    print(
        "TOP 10 RETURNING SNAP TOTALS"
    )
    print("-" * 60)

    highest = sorted(
        records,
        key=lambda record:
            record["returning_snaps"],
        reverse=True,
    )

    for record in highest[:10]:

        percent = record[
            "snapback_percent"
        ]

        percent_display = (
            f"{percent:.3f}"
            if percent is not None
            else "N/A"
        )

        print(
            f"{record['team']}: "
            f"snaps="
            f"{record['returning_snaps']:,}, "
            f"snapback="
            f"{percent_display}"
        )


if __name__ == "__main__":

    year = 2026

    if len(sys.argv) > 1:
        year = int(sys.argv[1])

    download_returning_snaps(
        year
    )
