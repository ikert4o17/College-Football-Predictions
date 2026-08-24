"""Project Gridiron 2026 in-season rating updater.

Always rebuilds from the frozen 2026 Balanced Light preseason ratings and every
completed 2026 FBS-vs-FBS result. Rebuilding from the immutable preseason prior
makes the process idempotent: a game can never be applied twice across weekly
workflow runs.

Usage:
    python -m ratings.inseason_ratings_2026
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from predictions.provisional_2026_predictions import load_margin_calibration

ROOT = Path(__file__).resolve().parent.parent
PRESEASON = ROOT / "data" / "processed" / "preseason_ratings_2026.json"
GAMES = ROOT / "data" / "raw" / "games.json"
OUTPUT = ROOT / "data" / "processed" / "inseason_ratings_2026.json"

# Temporary live-season V1 update parameters. These stay isolated here so the
# weekly operating system can run while the historical learning-rate backtest is
# revisited separately.
MAX_MARGIN_RESIDUAL = 28.0
MAX_TEAM_DELTA_PER_GAME = 4.0
BASE_LEARNING_RATE = 0.16
LEARNING_RATE_STEP = 0.03
MAX_LEARNING_RATE = 0.34


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


def fbs(game, side):
    return str(game.get(f"{side}Classification", "")).strip().lower() == "fbs"


def completed(game):
    hp, ap = game.get("homePoints"), game.get("awayPoints")
    dt = parse_date(game.get("startDate"))
    return hp is not None and ap is not None and dt is not None and dt < datetime.now(timezone.utc)


def clamp(value, low, high):
    return max(low, min(high, value))


def main():
    if not PRESEASON.exists():
        raise FileNotFoundError(
            f"Frozen Balanced Light preseason ratings are required: {PRESEASON}"
        )
    if not GAMES.exists():
        raise FileNotFoundError("Refreshed 2026 games are required.")

    preseason = load(PRESEASON)
    if isinstance(preseason, dict):
        preseason = preseason.get("ratings", [])
    games = load(GAMES)
    calibration = load_margin_calibration()
    coeff = float(calibration["rating_gap_coefficient"])
    hfa = float(calibration["home_field_advantage"])

    ratings = {}
    for row in preseason:
        team = row.get("team")
        if not team or row.get("power_rating") is None:
            continue
        ratings[team] = {
            **row,
            "preseason_power_rating": float(row["power_rating"]),
            "power_rating": float(row["power_rating"]),
            "games_inseason": 0,
            "inseason_adjustment": 0.0,
            "model_version": "2026_inseason_v1_balanced_light_prior",
        }

    eligible = []
    skipped_new_fbs = 0
    for game in games:
        if not isinstance(game, dict) or game.get("season") != 2026:
            continue
        if game.get("seasonType") != "regular" or not completed(game):
            continue
        if not (fbs(game, "home") and fbs(game, "away")):
            continue
        if game.get("homeTeam") not in ratings or game.get("awayTeam") not in ratings:
            skipped_new_fbs += 1
            continue
        eligible.append(game)

    eligible.sort(key=lambda g: parse_date(g.get("startDate")) or datetime.max.replace(tzinfo=timezone.utc))

    audit = []
    for game in eligible:
        home, away = game["homeTeam"], game["awayTeam"]
        hr, ar = ratings[home], ratings[away]
        neutral = bool(game.get("neutralSite"))
        expected = coeff * (hr["power_rating"] - ar["power_rating"]) + (0.0 if neutral else hfa)
        actual = float(game["homePoints"]) - float(game["awayPoints"])
        residual = clamp(actual - expected, -MAX_MARGIN_RESIDUAL, MAX_MARGIN_RESIDUAL)

        prior_games = (hr["games_inseason"] + ar["games_inseason"]) / 2.0
        learning = min(MAX_LEARNING_RATE, BASE_LEARNING_RATE + LEARNING_RATE_STEP * prior_games)
        raw_team_delta = 0.5 * learning * (residual / coeff)
        delta = clamp(raw_team_delta, -MAX_TEAM_DELTA_PER_GAME, MAX_TEAM_DELTA_PER_GAME)

        hr["power_rating"] += delta
        ar["power_rating"] -= delta
        hr["games_inseason"] += 1
        ar["games_inseason"] += 1

        audit.append({
            "game_id": game.get("id"),
            "week": game.get("week"),
            "home_team": home,
            "away_team": away,
            "actual_home_margin": round(actual, 2),
            "expected_home_margin": round(expected, 2),
            "capped_margin_residual": round(residual, 2),
            "learning_rate": round(learning, 4),
            "home_rating_delta": round(delta, 4),
            "away_rating_delta": round(-delta, 4),
        })

    output = []
    for row in ratings.values():
        row["power_rating"] = round(row["power_rating"], 4)
        row["inseason_adjustment"] = round(row["power_rating"] - row["preseason_power_rating"], 4)
        output.append(row)
    output.sort(key=lambda r: r["power_rating"], reverse=True)
    for rank, row in enumerate(output, 1):
        row["rank"] = rank

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "model_version": "2026_inseason_v1_balanced_light_prior",
        "preseason_source": str(PRESEASON.relative_to(ROOT)),
        "rebuild_mode": "idempotent_from_frozen_preseason",
        "ratings": output,
        "games_applied": audit,
    }, indent=4), encoding="utf-8")

    print("=" * 78)
    print("PROJECT GRIDIRON 2026 IN-SEASON RATINGS")
    print("=" * 78)
    print(f"Teams rated: {len(output)}")
    print(f"Completed FBS-vs-FBS games applied: {len(audit)}")
    print(f"Completed games skipped for teams without a preseason anchor: {skipped_new_fbs}")
    print(f"Saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
