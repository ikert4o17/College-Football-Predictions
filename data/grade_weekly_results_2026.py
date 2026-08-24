"""Grade Project Gridiron 2026 predictions against completed game results.

This module is intentionally run AFTER refreshing data/raw/games.json but BEFORE
replacing site_data/game_predictions_2026.json with the next slate. That means
the public prediction feed doubles as the immutable forecast source for games
that have just completed.

The grader is idempotent: each game_id is stored once in the cumulative ledger.
Repeated workflow runs will not double-count previously graded games.

Outputs:
    data/processed/model_performance_2026.json
    site_data/model_performance_2026.json
    data/snapshots/2026/results_week_<week>.json (when a week has graded games)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAMES = ROOT / "data" / "raw" / "games.json"
PREDICTIONS = ROOT / "site_data" / "game_predictions_2026.json"
OUTPUT = ROOT / "data" / "processed" / "model_performance_2026.json"
SITE_OUTPUT = ROOT / "site_data" / "model_performance_2026.json"
SNAPSHOT_DIR = ROOT / "data" / "snapshots" / "2026"


def load(path: Path, default=None):
    if not path.exists():
        return default
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


def is_completed(game):
    dt = parse_date(game.get("startDate"))
    return (
        game.get("homePoints") is not None
        and game.get("awayPoints") is not None
        and dt is not None
        and dt < datetime.now(timezone.utc)
    )


def mean(values):
    return round(sum(values) / len(values), 4) if values else None


def summarize(rows):
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

    return {
        "games": len(rows),
        "winner_accuracy": round(sum(1 for r in rows if r["winner_correct"]) / len(rows), 4),
        "margin_mae": mean([r["margin_abs_error"] for r in rows]),
        "margin_bias": mean([r["margin_error"] for r in rows]),
        "total_mae": mean([r["total_abs_error"] for r in rows]),
        "total_bias": mean([r["total_error"] for r in rows]),
        "score_mae": mean([r["score_mae"] for r in rows]),
    }


def main():
    games = load(GAMES, []) or []
    predictions = load(PREDICTIONS, []) or []
    previous = load(OUTPUT, {}) or {}
    ledger = {str(r.get("game_id")): r for r in previous.get("games", []) if r.get("game_id") is not None}

    game_lookup = {str(g.get("id")): g for g in games if isinstance(g, dict) and g.get("id") is not None}
    newly_graded = []

    for p in predictions:
        if not isinstance(p, dict) or p.get("season") != 2026 or p.get("game_id") is None:
            continue
        gid = str(p["game_id"])
        if gid in ledger:
            continue
        g = game_lookup.get(gid)
        if not g or not is_completed(g):
            continue

        hp = float(g["homePoints"])
        ap = float(g["awayPoints"])
        actual_margin = hp - ap
        actual_total = hp + ap
        projected_home_margin = float(p.get("projected_home_margin", 0.0))
        projected_total = float(p.get("projected_total", 0.0))
        phs = float(p.get("projected_home_score", p.get("home_score", 0.0)))
        pas = float(p.get("projected_away_score", p.get("away_score", 0.0)))

        if hp > ap:
            actual_winner = g.get("homeTeam")
        elif ap > hp:
            actual_winner = g.get("awayTeam")
        else:
            actual_winner = "Tie"

        row = {
            "season": 2026,
            "week": p.get("week", g.get("week")),
            "game_id": p["game_id"],
            "start_date": p.get("start_date", g.get("startDate")),
            "home_team": p.get("home_team", g.get("homeTeam")),
            "away_team": p.get("away_team", g.get("awayTeam")),
            "projected_winner": p.get("projected_winner"),
            "actual_winner": actual_winner,
            "winner_correct": p.get("projected_winner") == actual_winner,
            "projected_home_margin": round(projected_home_margin, 4),
            "actual_home_margin": round(actual_margin, 4),
            "margin_error": round(projected_home_margin - actual_margin, 4),
            "margin_abs_error": round(abs(projected_home_margin - actual_margin), 4),
            "projected_total": round(projected_total, 4),
            "actual_total": round(actual_total, 4),
            "total_error": round(projected_total - actual_total, 4),
            "total_abs_error": round(abs(projected_total - actual_total), 4),
            "projected_home_score": round(phs, 4),
            "actual_home_score": round(hp, 4),
            "projected_away_score": round(pas, 4),
            "actual_away_score": round(ap, 4),
            "score_mae": round((abs(phs - hp) + abs(pas - ap)) / 2.0, 4),
            "rating_model": p.get("rating_model"),
            "margin_calibration_model": p.get("margin_calibration_model"),
            "total_calibration_model": p.get("total_calibration_model"),
            "graded_at": datetime.now(timezone.utc).isoformat(),
        }
        ledger[gid] = row
        newly_graded.append(row)

    rows = sorted(ledger.values(), key=lambda r: (r.get("start_date") or "", str(r.get("game_id"))))
    by_week = {}
    for row in rows:
        key = str(row.get("week", "unknown"))
        by_week.setdefault(key, []).append(row)

    result = {
        "season": 2026,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metric_notes": {
            "winner_accuracy": "share of games where projected straight-up winner matched actual winner",
            "margin_mae": "mean absolute error of projected home margin versus actual home margin",
            "margin_bias": "mean projected home margin minus actual home margin; positive means model favored home side too much",
            "total_mae": "mean absolute error of projected total versus actual total",
            "total_bias": "mean projected total minus actual total; positive means model projected too many points",
            "score_mae": "mean absolute team-score error across home and away scores",
        },
        "cumulative": summarize(rows),
        "by_week": {week: summarize(week_rows) for week, week_rows in sorted(by_week.items(), key=lambda kv: kv[0])},
        "games": rows,
        "newly_graded_game_ids": [r["game_id"] for r in newly_graded],
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SITE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=4), encoding="utf-8")
    SITE_OUTPUT.write_text(json.dumps(result, indent=4), encoding="utf-8")

    touched_weeks = sorted({r.get("week") for r in newly_graded if r.get("week") is not None})
    for week in touched_weeks:
        week_rows = [r for r in rows if r.get("week") == week]
        snapshot = {
            "season": 2026,
            "week": week,
            "summary": summarize(week_rows),
            "games": week_rows,
        }
        (SNAPSHOT_DIR / f"results_week_{int(week):02d}.json").write_text(
            json.dumps(snapshot, indent=4), encoding="utf-8"
        )

    print("=" * 78)
    print("PROJECT GRIDIRON 2026 PREDICTION PERFORMANCE")
    print("=" * 78)
    print(f"Predictions currently in public feed: {len(predictions)}")
    print(f"Newly graded games: {len(newly_graded)}")
    print(f"Cumulative graded games: {len(rows)}")
    c = result["cumulative"]
    if c["games"]:
        print(f"Winner accuracy: {c['winner_accuracy']:.3f}")
        print(f"Margin MAE: {c['margin_mae']:.2f}")
        print(f"Total MAE: {c['total_mae']:.2f}")
        print(f"Score MAE: {c['score_mae']:.2f}")
    else:
        print("No completed published predictions to grade yet.")
    print(f"Saved: {OUTPUT}")
    print(f"Published: {SITE_OUTPUT}")


if __name__ == "__main__":
    main()
