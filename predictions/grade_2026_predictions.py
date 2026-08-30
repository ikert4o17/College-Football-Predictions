"""Grade published 2026 Project Gridiron predictions, including market results.

Core model performance remains FBS-vs-FBS only. Market grading uses CFBD's
historical betting-lines endpoint with provider=consensus. CFBD documents
`spread` and `overUnder`/`over_under` as closing values; opening values are
separate fields. If a verified consensus closing spread or total is absent,
that market is left ungraded rather than guessed.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
GAMES_FILE = ROOT / "data" / "raw" / "games.json"
PUBLISHED_PREDICTIONS = ROOT / "site_data" / "game_predictions_2026.json"
OUTPUT = ROOT / "data" / "processed" / "model_performance_2026.json"
SNAPSHOT_DIR = ROOT / "data" / "snapshots" / "2026"
SEASON = 2026
CFBD_LINES_URL = "https://api.collegefootballdata.com/lines"


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


def record(rows, key):
    results = [r.get(key) for r in rows if r.get(key) in {"W", "L", "P"}]
    return {
        "wins": results.count("W"),
        "losses": results.count("L"),
        "pushes": results.count("P"),
        "graded": len(results),
    }


def metrics(rows):
    if not rows:
        return {
            "games": 0, "winner_accuracy": None,
            "su_record": record([], "su_result"), "ats_record": record([], "ats_result"), "ou_record": record([], "ou_result"),
            "margin_mae": None, "margin_bias": None, "total_mae": None, "total_bias": None, "score_mae": None,
        }
    winner = [1.0 if r["winner_correct"] else 0.0 for r in rows if r.get("winner_correct") is not None]
    margin_abs = [abs(r["margin_error"]) for r in rows if r.get("margin_error") is not None]
    margin_bias = [r["margin_error"] for r in rows if r.get("margin_error") is not None]
    total_abs = [abs(r["total_error"]) for r in rows if r.get("total_error") is not None]
    total_bias = [r["total_error"] for r in rows if r.get("total_error") is not None]
    score_abs = []
    for r in rows:
        if r.get("home_score_error") is not None: score_abs.append(abs(r["home_score_error"]))
        if r.get("away_score_error") is not None: score_abs.append(abs(r["away_score_error"]))
    return {
        "games": len(rows), "winner_accuracy": mean(winner),
        "su_record": record(rows, "su_result"), "ats_record": record(rows, "ats_result"), "ou_record": record(rows, "ou_result"),
        "margin_mae": mean(margin_abs), "margin_bias": mean(margin_bias),
        "total_mae": mean(total_abs), "total_bias": mean(total_bias), "score_mae": mean(score_abs),
    }


def round_metrics(doc):
    out = {}
    for key, value in doc.items():
        out[key] = round(value, 4) if isinstance(value, float) else value
    return out


def fetch_consensus_closing_lines():
    token = os.getenv("CFBD_API_KEY")
    if not token:
        print("CFBD_API_KEY unavailable; market grading will preserve existing lines only.")
        return {}
    response = requests.get(
        CFBD_LINES_URL,
        params={"year": SEASON, "provider": "consensus"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    out = {}
    for game in payload if isinstance(payload, list) else []:
        game_id = game.get("id", game.get("gameId", game.get("game_id")))
        if game_id is None: continue
        lines = game.get("lines")
        if not isinstance(lines, list): lines = [game]
        chosen = next((x for x in lines if str(x.get("provider", "")).lower() == "consensus"), lines[0] if lines else {})
        spread = safe_float(chosen.get("spread"))
        total = safe_float(chosen.get("overUnder", chosen.get("over_under")))
        out[str(game_id)] = {
            "closing_spread": spread,
            "closing_total": total,
            "line_provider": chosen.get("provider") or "consensus",
        }
    print(f"Consensus closing-line games fetched: {len(out)}")
    return out


def apply_market_grade(row, market):
    if market:
        row["closing_spread"] = market.get("closing_spread")
        row["closing_total"] = market.get("closing_total")
        row["line_provider"] = market.get("line_provider") or "consensus"
    row["su_result"] = "W" if row.get("winner_correct") is True else "L" if row.get("winner_correct") is False else "P"

    close_spread = safe_float(row.get("closing_spread"))  # home-team spread; negative means home favored
    projected_margin = safe_float(row.get("projected_home_margin"))
    actual_margin = safe_float(row.get("actual_home_margin"))
    row["ats_pick"] = row["ats_result"] = None
    if close_spread is not None and projected_margin is not None and actual_margin is not None:
        market_home_margin = -close_spread
        edge = projected_margin - market_home_margin
        if abs(edge) > 1e-9:
            row["ats_pick"] = row.get("home_team") if edge > 0 else row.get("away_team")
            cover_margin = actual_margin + close_spread
            if abs(cover_margin) < 1e-9: row["ats_result"] = "P"
            elif (edge > 0 and cover_margin > 0) or (edge < 0 and cover_margin < 0): row["ats_result"] = "W"
            else: row["ats_result"] = "L"
        row["ats_edge"] = round(abs(edge), 4)
    else:
        row["ats_edge"] = None

    close_total = safe_float(row.get("closing_total"))
    projected_total = safe_float(row.get("projected_total"))
    actual_total = safe_float(row.get("actual_total"))
    row["ou_pick"] = row["ou_result"] = row["total_edge"] = None
    if close_total is not None and projected_total is not None and actual_total is not None:
        edge = projected_total - close_total
        if abs(edge) > 1e-9:
            row["ou_pick"] = "Over" if edge > 0 else "Under"
            if abs(actual_total - close_total) < 1e-9: row["ou_result"] = "P"
            elif (edge > 0 and actual_total > close_total) or (edge < 0 and actual_total < close_total): row["ou_result"] = "W"
            else: row["ou_result"] = "L"
        row["total_edge"] = round(abs(edge), 4)
    return row


def main():
    games = load(GAMES_FILE, [])
    published = load(PUBLISHED_PREDICTIONS, [])
    if isinstance(published, dict): published = published.get("predictions", published.get("games", []))
    previous = load(OUTPUT, {})
    previous_rows = list(previous.get("games", []))
    already = {str(r.get("game_id")) for r in previous_rows if r.get("game_id") is not None}
    games_by_id = {str(g.get("id")): g for g in games if isinstance(g, dict) and g.get("id") is not None and g.get("season") == SEASON}
    market_by_id = fetch_consensus_closing_lines()

    new_rows = []
    for pred in published:
        if not isinstance(pred, dict): continue
        game_id = pred.get("game_id")
        if game_id is None or str(game_id) in already: continue
        game = games_by_id.get(str(game_id))
        if game is None or not (is_fbs(game, "home") and is_fbs(game, "away")): continue
        score = complete_score(game)
        if score is None: continue
        actual_home, actual_away = score
        actual_margin, actual_total = actual_home - actual_away, actual_home + actual_away
        phm = safe_float(pred.get("projected_home_margin")); pt = safe_float(pred.get("projected_total"))
        phs = safe_float(pred.get("projected_home_score", pred.get("home_score"))); pas = safe_float(pred.get("projected_away_score", pred.get("away_score")))
        actual_winner = game.get("homeTeam") if actual_home > actual_away else game.get("awayTeam") if actual_away > actual_home else None
        projected_winner = pred.get("projected_winner")
        row = {
            "game_id": game_id, "week": game.get("week", pred.get("week")), "start_date": game.get("startDate", pred.get("start_date")),
            "home_team": game.get("homeTeam", pred.get("home_team")), "away_team": game.get("awayTeam", pred.get("away_team")),
            "actual_home_score": actual_home, "actual_away_score": actual_away, "actual_home_margin": actual_margin, "actual_total": actual_total,
            "projected_home_margin": phm, "projected_total": pt, "projected_home_score": phs, "projected_away_score": pas,
            "projected_winner": projected_winner, "actual_winner": actual_winner,
            "winner_correct": None if actual_winner is None or projected_winner is None else projected_winner == actual_winner,
            "margin_error": None if phm is None else phm - actual_margin, "total_error": None if pt is None else pt - actual_total,
            "home_score_error": None if phs is None else phs - actual_home, "away_score_error": None if pas is None else pas - actual_away,
            "model_version": pred.get("model_version", pred.get("rating_model")),
        }
        for key, value in list(row.items()):
            if isinstance(value, float): row[key] = round(value, 4)
        new_rows.append(apply_market_grade(row, market_by_id.get(str(game_id))))

    all_rows = previous_rows + new_rows
    # Backfill/refresh consensus closing lines for already graded games too.
    all_rows = [apply_market_grade(r, market_by_id.get(str(r.get("game_id")))) for r in all_rows]
    all_rows.sort(key=lambda r: (int(r.get("week") or 0), str(r.get("start_date") or ""), str(r.get("game_id") or "")))
    weeks = {}
    for row in all_rows:
        weeks.setdefault(str(row.get("week") if row.get("week") is not None else "unknown"), []).append(row)

    doc = {
        "season": SEASON, "generated_at": datetime.now(timezone.utc).isoformat(),
        "metric_notes": {
            "winner_accuracy": "share of games where projected straight-up winner matched actual winner",
            "su_record": "straight-up Project Gridiron winner record",
            "ats_record": "Project Gridiron side versus CFBD consensus closing spread; no verified line means no grade",
            "ou_record": "Project Gridiron over/under lean versus CFBD consensus closing total; no verified line means no grade",
            "market_source": "CFBD historical betting lines, provider=consensus; spread and total are documented closing values",
            "margin_mae": "mean absolute error of projected home margin versus actual home margin",
            "total_mae": "mean absolute error of projected total versus actual total",
            "scope": "core performance ledger grades FBS-vs-FBS predictions only; FBS-vs-FCS projections are projection-only",
        },
        "cumulative": round_metrics(metrics(all_rows)),
        "by_week": {week: round_metrics(metrics(rows)) for week, rows in weeks.items()},
        "games": all_rows, "newly_graded_game_ids": [r["game_id"] for r in new_rows],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True); OUTPUT.write_text(json.dumps(doc, indent=4), encoding="utf-8")
    if new_rows:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        for week in {int(r.get("week") or 0) for r in new_rows}:
            rows = [r for r in new_rows if int(r.get("week") or 0) == week]
            path = SNAPSHOT_DIR / f"results_week_{week:02d}.json"; existing = load(path, [])
            ids = {str(r.get("game_id")) for r in existing if isinstance(r, dict)}
            path.write_text(json.dumps(existing + [r for r in rows if str(r.get("game_id")) not in ids], indent=4), encoding="utf-8")
    print("=" * 78); print("PROJECT GRIDIRON 2026 PREDICTION + MARKET GRADER"); print("=" * 78)
    print(f"Published predictions inspected: {len(published)}"); print(f"Newly graded FBS-vs-FBS games: {len(new_rows)}")
    print(f"Cumulative graded games: {len(all_rows)}"); print(f"Saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
