"""Generate upcoming 2026 Project Gridiron predictions.

FBS-vs-FBS games use the production Project Gridiron model.
FBS-vs-FCS games are projection-only: the FCS team's CFBD Elo is translated
onto the current Project Gridiron scale using a cross-sectional FBS
Elo-to-rating bridge. These games NEVER feed the FBS rating updater.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from data.cfbd_api import client
from predictions import provisional_2026_predictions as base

ROOT = Path(__file__).resolve().parent.parent
RATINGS = ROOT / "data" / "processed" / "inseason_ratings_2026.json"
GAMES = ROOT / "data" / "raw" / "games.json"
OUTPUT = ROOT / "data" / "processed" / "game_predictions_2026.json"
LOOKAHEAD_DAYS = 8
MIN_ELO_BRIDGE_TEAMS = 25


def load(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def parse_date(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def classification(game, side):
    return str(game.get(f"{side}Classification", "")).strip().lower()


def safe_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def fetch_current_elos():
    """Fetch one season-wide Elo snapshot when CFBD credentials are available."""
    if not os.getenv("CFBD_API_KEY"):
        return {}
    try:
        rows = client.get(
            "/ratings/elo",
            params={"year": 2026, "seasonType": "regular"},
        )
    except Exception as exc:
        print(f"WARNING: CFBD Elo fallback unavailable: {exc}")
        return {}

    lookup = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        team = row.get("team")
        elo = safe_float(row.get("elo"))
        if team and elo is not None:
            lookup[team] = elo
    return lookup


def build_elo_bridge(games, rating_lookup, now, elo_lookup=None):
    """Fit current Project Gridiron rating = intercept + slope * CFBD Elo."""
    latest = {}
    for game in games:
        if not isinstance(game, dict) or game.get("season") != 2026:
            continue
        dt = parse_date(game.get("startDate"))
        if dt is None:
            continue
        for side in ("home", "away"):
            if classification(game, side) != "fbs":
                continue
            team = game.get(f"{side}Team")
            elo = safe_float(game.get(f"{side}PregameElo"))
            if not team or elo is None or team not in rating_lookup:
                continue
            past = dt <= now
            key = (1 if past else 0, dt.timestamp() if past else -dt.timestamp())
            if team not in latest or key > latest[team][0]:
                latest[team] = (key, elo)

    pairs = []
    for team, record in rating_lookup.items():
        elo = None
        if elo_lookup:
            elo = safe_float(elo_lookup.get(team))
        if elo is None and team in latest:
            elo = latest[team][1]
        rating = safe_float(record.get("power_rating"))
        if elo is not None and rating is not None:
            pairs.append((elo, rating))

    if len(pairs) < MIN_ELO_BRIDGE_TEAMS:
        return None

    mean_x = sum(x for x, _ in pairs) / len(pairs)
    mean_y = sum(y for _, y in pairs) / len(pairs)
    variance = sum((x - mean_x) ** 2 for x, _ in pairs)
    if variance <= 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in pairs) / variance
    intercept = mean_y - slope * mean_x
    return {"intercept": intercept, "slope": slope, "teams": len(pairs)}


def project_fbs_fcs(game, rating_lookup, margin, elo_bridge, elo_lookup=None):
    """Project an FBS-vs-FCS spread without touching the production FBS model."""
    hc, ac = classification(game, "home"), classification(game, "away")
    if {hc, ac} != {"fbs", "fcs"} or elo_bridge is None:
        return None

    home, away = game.get("homeTeam"), game.get("awayTeam")
    fbs_side = "home" if hc == "fbs" else "away"
    fcs_side = "away" if fbs_side == "home" else "home"
    fbs_team = game.get(f"{fbs_side}Team")
    fcs_team = game.get(f"{fcs_side}Team")
    fcs_elo = safe_float(game.get(f"{fcs_side}PregameElo"))
    elo_source = "game pregame Elo"
    if fcs_elo is None and elo_lookup:
        fcs_elo = safe_float(elo_lookup.get(fcs_team))
        elo_source = "CFBD /ratings/elo season snapshot"

    fbs_record = rating_lookup.get(fbs_team)
    if fbs_record is None or fcs_elo is None:
        return None

    fbs_rating = safe_float(fbs_record.get("power_rating"))
    if fbs_rating is None:
        return None
    fcs_rating = elo_bridge["intercept"] + elo_bridge["slope"] * fcs_elo
    home_rating = fbs_rating if fbs_side == "home" else fcs_rating
    away_rating = fcs_rating if fbs_side == "home" else fbs_rating

    components = base.calculate_projected_home_margin(
        home_rating, away_rating, bool(game.get("neutralSite")), margin
    )
    home_margin = components["projected_home_margin"]
    winner = home if home_margin > 0 else away if home_margin < 0 else None

    return {
        "season": 2026,
        "game_id": game.get("id"),
        "week": game.get("week"),
        "start_date": game.get("startDate"),
        "neutral_site": bool(game.get("neutralSite")),
        "venue": game.get("venue"),
        "home_team": home,
        "away_team": away,
        "home_classification": hc,
        "away_classification": ac,
        "home_rating": round(home_rating, 4),
        "away_rating": round(away_rating, 4),
        "projected_home_margin": round(home_margin, 2),
        "projected_winner": winner,
        "projected_margin": round(abs(home_margin), 2),
        "projected_total": None,
        "projected_home_score": None,
        "projected_away_score": None,
        "provisional": False,
        "rating_model": "2026_fbs_fcs_projection_only_v2",
        "projection_type": "fbs_fcs",
        "fcs_projection_only": True,
        "affects_fbs_ratings": False,
        "fcs_rating_source": f"CFBD Elo translated to Project Gridiron scale ({elo_source})",
        "elo_bridge_teams": elo_bridge["teams"],
    }


def main():
    if not RATINGS.exists() or not GAMES.exists():
        raise FileNotFoundError("In-season ratings and refreshed games are required.")

    rating_data = load(RATINGS)
    rating_rows = rating_data.get("ratings", rating_data if isinstance(rating_data, list) else [])
    rating_lookup = base.build_rating_lookup(rating_rows)
    games = load(GAMES)
    margin = base.load_margin_calibration()
    total = base.load_total_calibration()

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=LOOKAHEAD_DAYS)
    elo_lookup = fetch_current_elos()
    elo_bridge = build_elo_bridge(games, rating_lookup, now, elo_lookup)
    predictions = []
    skipped_missing = 0
    fcs_count = 0

    for game in games:
        if not isinstance(game, dict) or game.get("season") != 2026:
            continue
        if game.get("seasonType") != "regular":
            continue
        start = parse_date(game.get("startDate"))
        if start is None or start < now or start > end:
            continue

        hc, ac = classification(game, "home"), classification(game, "away")
        projection = None
        if hc == "fbs" and ac == "fbs":
            projection = base.project_game(game, rating_lookup, margin, total)
            if projection is not None:
                projection["provisional"] = False
                projection["rating_model"] = "2026_inseason_v2"
                projection["projection_type"] = "fbs_fbs"
                projection["affects_fbs_ratings"] = True
        elif {hc, ac} == {"fbs", "fcs"}:
            projection = project_fbs_fcs(game, rating_lookup, margin, elo_bridge, elo_lookup)
            if projection is not None:
                fcs_count += 1

        if projection is None:
            if hc == "fbs" or ac == "fbs":
                skipped_missing += 1
            continue
        predictions.append(projection)

    predictions.sort(key=lambda r: r.get("start_date") or "")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(predictions, indent=4), encoding="utf-8")

    print("=" * 78)
    print("PROJECT GRIDIRON 2026 WEEKLY PREDICTIONS")
    print("=" * 78)
    print(f"Window: {now.isoformat()} through {end.isoformat()}")
    print(f"FBS ratings loaded: {len(rating_lookup)}")
    print(f"CFBD Elo teams loaded: {len(elo_lookup)}")
    print(f"Predictions generated: {len(predictions)}")
    print(f"FBS-FCS projection-only games: {fcs_count}")
    print(f"Elo bridge teams: {elo_bridge['teams'] if elo_bridge else 0}")
    print(f"Eligible games skipped for missing projection data: {skipped_missing}")
    print(f"Saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
