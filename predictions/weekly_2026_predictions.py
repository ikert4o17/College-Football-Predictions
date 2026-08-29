"""Generate upcoming 2026 Project Gridiron predictions.

FBS-vs-FBS games use the production Project Gridiron model unchanged.
FBS-vs-FCS games are projection-only. FCS strength is translated onto the
Project Gridiron scale from CFBD cross-division ratings and NEVER feeds the
FBS rating updater.
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
MIN_BRIDGE_TEAMS = 25


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


def linear_bridge(source_lookup, rating_lookup):
    """Fit Project Gridiron rating = intercept + slope * source rating."""
    pairs = []
    for team, record in rating_lookup.items():
        x = safe_float(source_lookup.get(team))
        y = safe_float(record.get("power_rating"))
        if x is not None and y is not None:
            pairs.append((x, y))
    if len(pairs) < MIN_BRIDGE_TEAMS:
        return None
    mean_x = sum(x for x, _ in pairs) / len(pairs)
    mean_y = sum(y for _, y in pairs) / len(pairs)
    variance = sum((x - mean_x) ** 2 for x, _ in pairs)
    if variance <= 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in pairs) / variance
    return {"intercept": mean_y - slope * mean_x, "slope": slope, "teams": len(pairs)}


def fetch_elo():
    """Fetch CFBD Elo. Elo is useful for FBS bridging but may omit FCS teams."""
    if not os.getenv("CFBD_API_KEY"):
        return {}
    try:
        rows = client.get("/ratings/elo", params={"year": 2026, "seasonType": "regular"})
    except Exception as exc:
        print(f"WARNING: CFBD Elo unavailable: {exc}")
        return {}
    out = {}
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and row.get("team") and safe_float(row.get("elo")) is not None:
            out[row["team"]] = float(row["elo"])
    return out


def fetch_expanded_srs(year, division):
    """Fetch CFBD expanded SRS, whose documented classification supports FBS/FCS."""
    if not os.getenv("CFBD_API_KEY"):
        return {}
    try:
        rows = client.get(
            "/ratings/srs/expanded",
            params={"year": year, "classification": division},
        )
    except Exception as exc:
        print(f"WARNING: CFBD expanded SRS {year} {division} unavailable: {exc}")
        return {}
    out = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("team"):
            continue
        rating = safe_float(row.get("rating"))
        if rating is not None:
            out[row["team"]] = rating
    return out


def game_pregame_elo(game, side):
    return safe_float(game.get(f"{side}PregameElo"))


def build_projection_sources(games, rating_lookup, now):
    """Build multiple independent cross-division bridges with graceful fallbacks."""
    elo = fetch_elo()

    # Supplement Elo with the most useful pregame Elo embedded in game records.
    latest_game_elo = {}
    for game in games:
        if not isinstance(game, dict) or game.get("season") != 2026:
            continue
        dt = parse_date(game.get("startDate"))
        if dt is None:
            continue
        for side in ("home", "away"):
            team = game.get(f"{side}Team")
            value = game_pregame_elo(game, side)
            if not team or value is None:
                continue
            past = dt <= now
            key = (1 if past else 0, dt.timestamp() if past else -dt.timestamp())
            if team not in latest_game_elo or key > latest_game_elo[team][0]:
                latest_game_elo[team] = (key, value)
    for team, (_, value) in latest_game_elo.items():
        elo.setdefault(team, value)

    srs_2026_fbs = fetch_expanded_srs(2026, "fbs")
    srs_2026_fcs = fetch_expanded_srs(2026, "fcs")
    srs_2025_fbs = fetch_expanded_srs(2025, "fbs")
    srs_2025_fcs = fetch_expanded_srs(2025, "fcs")

    return {
        "elo": {"ratings": elo, "bridge": linear_bridge(elo, rating_lookup)},
        "srs_2026": {
            "fbs": srs_2026_fbs,
            "fcs": srs_2026_fcs,
            "bridge": linear_bridge(srs_2026_fbs, rating_lookup),
        },
        "srs_2025": {
            "fbs": srs_2025_fbs,
            "fcs": srs_2025_fcs,
            "bridge": linear_bridge(srs_2025_fbs, rating_lookup),
        },
    }


def translated_fcs_rating(game, fcs_side, sources):
    """Return best available FCS rating translated to Project Gridiron scale."""
    team = game.get(f"{fcs_side}Team")

    # 1) Pregame Elo on the exact game, if CFBD supplies it.
    elo = game_pregame_elo(game, fcs_side)
    bridge = sources["elo"]["bridge"]
    if elo is not None and bridge:
        return bridge["intercept"] + bridge["slope"] * elo, "CFBD game pregame Elo", bridge["teams"]

    # 2) Season Elo snapshot, when the FCS team is included.
    elo = safe_float(sources["elo"]["ratings"].get(team))
    if elo is not None and bridge:
        return bridge["intercept"] + bridge["slope"] * elo, "CFBD 2026 Elo", bridge["teams"]

    # 3) Current-season expanded SRS. CFBD explicitly supports FCS here.
    current = sources["srs_2026"]
    srs = safe_float(current["fcs"].get(team))
    bridge = current["bridge"]
    if srs is not None and bridge:
        return bridge["intercept"] + bridge["slope"] * srs, "CFBD 2026 expanded SRS", bridge["teams"]

    # 4) Prior-season expanded SRS gives every returning FCS program a stable
    # preseason fallback before it has enough 2026 data for a current rating.
    prior = sources["srs_2025"]
    srs = safe_float(prior["fcs"].get(team))
    bridge = prior["bridge"]
    if srs is not None and bridge:
        return bridge["intercept"] + bridge["slope"] * srs, "CFBD 2025 expanded SRS fallback", bridge["teams"]

    return None


def project_fbs_fcs(game, rating_lookup, margin, sources):
    hc, ac = classification(game, "home"), classification(game, "away")
    if {hc, ac} != {"fbs", "fcs"}:
        return None

    home, away = game.get("homeTeam"), game.get("awayTeam")
    fbs_side = "home" if hc == "fbs" else "away"
    fcs_side = "away" if fbs_side == "home" else "home"
    fbs_team = game.get(f"{fbs_side}Team")
    fcs_info = translated_fcs_rating(game, fcs_side, sources)
    fbs_record = rating_lookup.get(fbs_team)
    if fbs_record is None or fcs_info is None:
        return None

    fcs_rating, source_label, bridge_teams = fcs_info
    fbs_rating = safe_float(fbs_record.get("power_rating"))
    if fbs_rating is None:
        return None
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
        "rating_model": "2026_fbs_fcs_projection_only_v3",
        "projection_type": "fbs_fcs",
        "fcs_projection_only": True,
        "affects_fbs_ratings": False,
        "fcs_rating_source": source_label,
        "bridge_teams": bridge_teams,
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
    sources = build_projection_sources(games, rating_lookup, now)
    predictions = []
    skipped_missing = 0
    fcs_count = 0
    fcs_candidates = 0

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
            fcs_candidates += 1
            projection = project_fbs_fcs(game, rating_lookup, margin, sources)
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
    print(f"Predictions generated: {len(predictions)}")
    print(f"FBS-FCS candidates: {fcs_candidates}")
    print(f"FBS-FCS projection-only games: {fcs_count}")
    print(f"2026 FCS expanded SRS teams: {len(sources['srs_2026']['fcs'])}")
    print(f"2025 FCS expanded SRS teams: {len(sources['srs_2025']['fcs'])}")
    print(f"Eligible games skipped for missing projection data: {skipped_missing}")
    print(f"Saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
