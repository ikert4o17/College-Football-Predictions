"""Capture current NCAAF spreads/totals and preserve a Project Gridiron market archive.

The Odds API current NCAAF feed is used only for live/upcoming prices. Each run
matches provider events to CFBD game IDs, computes a median consensus across
available US books, and appends a timestamped pre-kickoff snapshot. The final
snapshot strictly before kickoff is the official Project Gridiron closing line.
"""

import json
import os
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
GAMES_FILE = ROOT / "data" / "raw" / "games.json"
ARCHIVE_FILE = ROOT / "data" / "market" / "market_archive_2026.json"
SEASON = 2026
ODDS_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf/odds"


def load(path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def norm(value):
    value = str(value or "").lower().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


ALIASES = {
    "miami fl": ["miami hurricanes", "miami florida"],
    "miami oh": ["miami ohio", "miami redhawks"],
    "nc state": ["north carolina state", "nc state wolfpack"],
    "north carolina": ["north carolina tar heels"],
    "usc": ["southern california", "usc trojans"],
    "uconn": ["connecticut huskies", "connecticut"],
    "umass": ["massachusetts minutemen", "massachusetts"],
    "utep": ["utep miners", "texas el paso"],
    "utsa": ["utsa roadrunners", "texas san antonio"],
    "tcu": ["tcu horned frogs", "texas christian"],
    "smu": ["smu mustangs", "southern methodist"],
    "ucf": ["ucf knights", "central florida"],
    "uab": ["uab blazers", "alabama birmingham"],
    "byu": ["byu cougars", "brigham young"],
    "lsu": ["lsu tigers", "louisiana state"],
    "ole miss": ["mississippi rebels", "ole miss rebels"],
    "san jose state": ["san jose state spartans", "san jos state spartans"],
}


def team_match(cfbd_name, odds_name):
    a, b = norm(cfbd_name), norm(odds_name)
    if not a or not b:
        return False
    if a == b or b.startswith(a + " ") or a.startswith(b + " "):
        return True
    variants = [norm(x) for x in ALIASES.get(a, [])]
    return b in variants or any(b.startswith(v + " ") or v.startswith(b + " ") for v in variants)


def candidate_games(games, commence):
    if commence is None:
        return []
    out = []
    for game in games:
        if not isinstance(game, dict) or game.get("season") != SEASON:
            continue
        start = parse_dt(game.get("startDate"))
        if start is None:
            continue
        if abs((start - commence).total_seconds()) <= 3 * 3600:
            out.append(game)
    return out


def match_game(games, event):
    commence = parse_dt(event.get("commence_time"))
    home, away = event.get("home_team"), event.get("away_team")
    matches = []
    for game in candidate_games(games, commence):
        direct = team_match(game.get("homeTeam"), home) and team_match(game.get("awayTeam"), away)
        swapped = team_match(game.get("homeTeam"), away) and team_match(game.get("awayTeam"), home)
        if direct or swapped:
            matches.append((game, swapped))
    return matches[0] if len(matches) == 1 else (None, False)


def market_values(event):
    books = []
    home_name = event.get("home_team")
    for book in event.get("bookmakers", []):
        row = {"key": book.get("key"), "title": book.get("title"), "last_update": book.get("last_update")}
        for market in book.get("markets", []):
            key = market.get("key")
            outcomes = market.get("outcomes", [])
            if key == "spreads":
                home_outcome = next((o for o in outcomes if team_match(home_name, o.get("name"))), None)
                if home_outcome and home_outcome.get("point") is not None:
                    row["home_spread"] = float(home_outcome["point"])
            elif key == "totals":
                over = next((o for o in outcomes if str(o.get("name", "")).lower() == "over"), None)
                if over and over.get("point") is not None:
                    row["total"] = float(over["point"])
        if "home_spread" in row or "total" in row:
            books.append(row)
    spreads = [b["home_spread"] for b in books if "home_spread" in b]
    totals = [b["total"] for b in books if "total" in b]
    return books, (statistics.median(spreads) if spreads else None), (statistics.median(totals) if totals else None)


def main():
    token = os.getenv("ODDS_API_KEY")
    if not token:
        raise RuntimeError("ODDS_API_KEY is required")

    response = requests.get(
        ODDS_URL,
        params={
            "apiKey": token,
            "regions": "us",
            "markets": "spreads,totals",
            "oddsFormat": "american",
            "dateFormat": "iso",
        },
        timeout=30,
    )
    response.raise_for_status()
    events = response.json()
    games = load(GAMES_FILE, [])
    archive = load(ARCHIVE_FILE, {"season": SEASON, "source": "the_odds_api", "games": {}})
    archive.setdefault("games", {})

    now = datetime.now(timezone.utc)
    captured = matched = skipped_live = 0
    unmatched = []

    for event in events if isinstance(events, list) else []:
        commence = parse_dt(event.get("commence_time"))
        if commence is None or commence <= now:
            skipped_live += 1
            continue
        game, swapped = match_game(games, event)
        if game is None:
            unmatched.append({"home": event.get("home_team"), "away": event.get("away_team"), "commence_time": event.get("commence_time")})
            continue
        matched += 1
        books, spread, total = market_values(event)
        if swapped and spread is not None:
            spread = -spread
        if spread is None and total is None:
            continue

        game_id = str(game.get("id"))
        entry = archive["games"].setdefault(game_id, {
            "game_id": game.get("id"),
            "week": game.get("week"),
            "home_team": game.get("homeTeam"),
            "away_team": game.get("awayTeam"),
            "start_date": game.get("startDate"),
            "provider_event_id": event.get("id"),
            "snapshots": [],
        })
        snapshot = {
            "captured_at": now.isoformat(),
            "commence_time": event.get("commence_time"),
            "consensus_home_spread": spread,
            "consensus_total": total,
            "spread_books": sum("home_spread" in b for b in books),
            "total_books": sum("total" in b for b in books),
            "books": books,
        }
        entry.setdefault("snapshots", []).append(snapshot)
        entry["latest_pre_kickoff"] = snapshot
        captured += 1

    archive["generated_at"] = now.isoformat()
    archive["source"] = "the_odds_api"
    archive["consensus_method"] = "median across available US bookmakers; final strictly pre-kickoff snapshot is official close"
    archive["last_capture"] = {
        "events_returned": len(events) if isinstance(events, list) else 0,
        "matched": matched,
        "captured": captured,
        "skipped_live": skipped_live,
        "unmatched_count": len(unmatched),
        "unmatched_sample": unmatched[:20],
        "requests_remaining": response.headers.get("x-requests-remaining"),
        "requests_used": response.headers.get("x-requests-used"),
        "request_cost": response.headers.get("x-requests-last"),
    }

    ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVE_FILE.write_text(json.dumps(archive, indent=2), encoding="utf-8")
    print("=" * 78)
    print("PROJECT GRIDIRON 2026 MARKET SNAPSHOT")
    print("=" * 78)
    print(f"Odds events returned: {archive['last_capture']['events_returned']}")
    print(f"Matched to CFBD games: {matched}")
    print(f"Snapshots captured: {captured}")
    print(f"Unmatched events: {len(unmatched)}")
    print(f"API request cost: {archive['last_capture']['request_cost']}")
    print(f"API requests remaining: {archive['last_capture']['requests_remaining']}")
    print(f"Saved to: {ARCHIVE_FILE}")


if __name__ == "__main__":
    main()
