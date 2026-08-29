"""Grade previously published 2026 Project Gridiron predictions.

The weekly workflow refreshes game results first, then this module grades only
predictions that were already published before the new slate is generated.
FBS-vs-FCS projection-only games are intentionally excluded from the core
Project Gridiron performance ledger.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAMES_FILE = ROOT / "data" / "raw" / "games.json"
PUBLISHED_PREDICTIONS = ROOT / "site_data" / "game_predictions_2026.json"
OUTPUT = ROOT / "data" / "processed" / "model_performance_2026.json"
SNAPSHOT_DIR = ROOT / "data" / "snapshots" / "2026"
SEASON = 2026


def load(path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_fbs(game, side):
    return str(game.get(f"{side}Classification", "")).strip().lower() == "fbs"


def complete_score(game):
    home = safe_float(game.get("homePoints"))
    away = safe_float(game.get("awayPoints"))
    if home is None or away is None:
        return None
    return home, away


def mean(values):
    return sum(values) / len(values) if values else None


def metrics(rows):
    if not rows:
        return {
            "games": 0,
            "winner_accuracy": None,
            "margin_mae": None,
            "margin_bias": None,
            "total_mae": None,
            "total_bias": None,
            "score_mae": None,
        }

    winner = [1.0 if r["winner_correct"] else 0.0 for r in rows if r.get("winner_correct") is not None]
    margin_abs = [abs(r["margin_error"]) for r in rows if r.get("margin_error") is not None]
    margin_bias = [r["margin_error"] for r in rows if r.get("margin_error") is not None]
    total_abs = [abs(r["total_error"]) for r in rows if r.get("total_error") is not None]
    total_bias = [r["total_error"] for r in rows if r.get("total_error") is not None]
    score_abs = []
    for r in rows:
        if r.get("home_score_error") is not None:
            score_abs.append(abs(r["home_score_error"]))
        if r.get("away_score_error") is not None:
            score_abs.append(abs(r["away_score_error"]))

    return {
        "games": len(rows),
        "winner_accuracy": mean(winner),
        "margin_mae": mean(margin_abs),
        "margin_bias": mean(margin_bias),
        "total_mae": mean(total_abs),
        "total_bias": mean(total_bias),
        "score_mae": mean(score_abs),
    }


def round_metrics(doc):
    out = dict(doc)
    for key, value in list(out.items()):
        if isinstance(value, float):
            out[key] = round(value, 4)
    return out


def main():
    games = load(GAMES_FILE, [])
    published = load(PUBLISHED_PREDICTIONS, [])
    if isinstance(published, dict):
        published = published.get("predictions", published.get("games", []))

    previous = load(OUTPUT, {})
    already = {
        str(row.get("game_id"))
        for row in previous.get("games", [])
        if row.get("game_id") is not None
    }

    games_by_id = {
        str(g.get("id")): g
        for g in games
        if isinstance(g, dict) and g.get("id") is not None and g.get("season") == SEASON
    }

    new_rows = []
    for pred in published:
        if not isinstance(pred, dict):
            continue
        game_id = pred.get("game_id")
        if game_id is None or str(game_id) in already:
            continue
        game = games_by_id.get(str(game_id))
        if game is None or not (is_fbs(game, "home") and is_fbs(game, "away")):
            continue
        score = complete_score(game)
        if score is None:
            continue

        actual_home, actual_away = score
        actual_margin = actual_home - actual_away
        actual_total = actual_home + actual_away
        projected_home_margin = safe_float(pred.get("projected_home_margin"))
        projected_total = safe_float(pred.get("projected_total"))
        projected_home_score = safe_float(pred.get("projected_home_score", pred.get("home_score")))
        projected_away_score = safe_float(pred.get("projected_away_score", pred.get("away_score")))

        actual_winner = game.get("homeTeam") if actual_home > actual_away else game.get("awayTeam") if actual_away > actual_home else None
        projected_winner = pred.get("projected_winner")

        row = {
            "game_id": game_id,
            "week": game.get("week", pred.get("week")),
            "start_date": game.get("startDate", pred.get("start_date")),
            "home_team": game.get("homeTeam", pred.get("home_team")),
            "away_team": game.get("awayTeam", pred.get("away_team")),
            "actual_home_score": actual_home,
            "actual_away_score": actual_away,
            "actual_home_margin": actual_margin,
            "actual_total": actual_total,
            "projected_home_margin": projected_home_margin,
            "projected_total": projected_total,
            "projected_home_score": projected_home_score,
            "projected_away_score": projected_away_score,
            "projected_winner": projected_winner,
            "actual_winner": actual_winner,
            "winner_correct": None if actual_winner is None or projected_winner is None else projected_winner == actual_winner,
            "margin_error": None if projected_home_margin is None else projected_home_margin - actual_margin,
            "total_error": None if projected_total is None else projected_total - actual_total,
            "home_score_error": None if projected_home_score is None else projected_home_score - actual_home,
            "away_score_error": None if projected_away_score is None else projected_away_score - actual_away,
            "model_version": pred.get("model_version", pred.get("rating_model")),
        }
        for key in ("actual_home_score", "actual_away_score", "actual_home_margin", "actual_total", "projected_home_margin", "projected_total", "projected_home_score", "projected_away_score", "margin_error", "total_error", "home_score_error", "away_score_error"):
            if isinstance(row.get(key), float):
                row[key] = round(row[key], 4)
        new_rows.append(row)

    all_rows = list(previous.get("games", [])) + new_rows
    all_rows.sort(key=lambda r: (int(r.get("week") or 0), str(r.get("start_date") or ""), str(r.get("game_id") or "")))

    weeks = {}
    for row in all_rows:
        key = str(row.get("week") if row.get("week") is not None else "unknown")
        weeks.setdefault(key, []).append(row)

    doc = {
        "season": SEASON,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metric_notes": {
            "winner_accuracy": "share of games where projected straight-up winner matched actual winner",
            "margin_mae": "mean absolute error of projected home margin versus actual home margin",
            "margin_bias": "mean projected home margin minus actual home margin; positive means model favored home side too much",
            "total_mae": "mean absolute error of projected total versus actual total",
            "total_bias": "mean projected total minus actual total; positive means model projected too many points",
            "score_mae": "mean absolute team-score error across home and away scores",
            "scope": "core performance ledger grades FBS-vs-FBS predictions only; FBS-vs-FCS projections are projection-only",
        },
        "cumulative": round_metrics(metrics(all_rows)),
        "by_week": {week: round_metrics(metrics(rows)) for week, rows in weeks.items()},
        "games": all_rows,
        "newly_graded_game_ids": [row["game_id"] for row in new_rows],
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(doc, indent=4), encoding="utf-8")

    if new_rows:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        by_week_new = {}
        for row in new_rows:
            week = int(row.get("week") or 0)
            by_week_new.setdefault(week, []).append(row)
        for week, rows in by_week_new.items():
            path = SNAPSHOT_DIR / f"results_week_{week:02d}.json"
            existing = load(path, [])
            existing_ids = {str(r.get("game_id")) for r in existing if isinstance(r, dict)}
            merged = existing + [r for r in rows if str(r.get("game_id")) not in existing_ids]
            path.write_text(json.dumps(merged, indent=4), encoding="utf-8")

    print("=" * 78)
    print("PROJECT GRIDIRON 2026 PREDICTION GRADER")
    print("=" * 78)
    print(f"Published predictions inspected: {len(published)}")
    print(f"Newly graded FBS-vs-FBS games: {len(new_rows)}")
    print(f"Cumulative graded games: {len(all_rows)}")
    print(f"Saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
