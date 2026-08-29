"""Generate upcoming 2026 Project Gridiron predictions.

FBS-vs-FBS games use the production Project Gridiron model.
FBS-vs-FCS games are projection-only: the FCS team's CFBD pregame Elo is
translated onto the current Project Gridiron scale using a cross-sectional
FBS Elo-to-rating bridge. These games NEVER feed the FBS rating updater.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


def build_elo_bridge(games, rating_lookup, now):
    """Fit current Project Gridiron rating = intercept + slope * CFBD Elo.

    Uses the most recent available 2026 pregame Elo for each anchored FBS team.
    This keeps FCS teams on a comparable projection scale without adding them to
    the core rating system or allowing FBS-FCS results to alter FBS ratings.
    """
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
            # Prefer the closest already-started game; if none exists, retain
            # the earliest future preseason Elo as a fallback.
            past = dt <= now
            key = (1 if past else 0, dt.timestamp() if past else -dt.timestamp())
            if team not in latest or key > latest[team][0]:
                latest[team] = (key, elo)

    pairs = []
    for team, (_, elo) in latest.items():
        rating = safe_float(rating_lookup[team].get("power_rating"))
        if rating is not None:
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


def project_fbs_fcs(game, rating_lookup, margin, elo_bridge):
    """Project an FBS-vs-FCS spread without touching the production FBS model."""
    hc, ac = classification(game, "home"), classification(game, "away")
    if {hc, ac} != {"fbs", "fcs"} or elo_bridge is None:
        return None

    home, away = game.get("homeTeam"), game.get("awayTeam")
    fbs_side = "home" if hc == "fbs" else "away"
    fcs_side = "away" if fbs_side == "home" else "home"
    fbs_team = game.get(f"{fbs_side}Team")
    fcs_elo = safe_float(game.get(f"{fcs_side}PregameElo"))
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
        "rating_model": "2026_fbs_fcs_projection_only_v1",
        "projection_type": "fbs_fcs",
        "fcs_projection_only": True,
        "affects_fbs_ratings": False,
        "fcs_rating_source": "CFBD pregame Elo translated to Project Gridiron scale",
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
    elo_bridge = build_elo_bridge(games, rating_lookup, now)
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
            projection = project_fbs_fcs(game, rating_lookup, margin, elo_bridge)
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
    print(f"FBS-FCS projection-only games: {fcs_count}")
    print(f"Elo bridge teams: {elo_bridge['teams'] if elo_bridge else 0}")
    print(f"Eligible games skipped for missing projection data: {skipped_missing}")
    print(f"Saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
