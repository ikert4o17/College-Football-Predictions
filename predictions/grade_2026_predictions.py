"""Grade published 2026 Project Gridiron predictions.

Core performance is FBS-vs-FBS only. ATS and O/U grading uses the immutable
Project Gridiron market archive. The official close is the last captured
snapshot strictly before kickoff, with consensus defined as the median across
available US bookmakers from The Odds API.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAMES_FILE = ROOT / "data" / "raw" / "games.json"
PUBLISHED_PREDICTIONS = ROOT / "site_data" / "game_predictions_2026.json"
MARKET_ARCHIVE = ROOT / "data" / "market" / "market_archive_2026.json"
OUTPUT = ROOT / "data" / "processed" / "model_performance_2026.json"
SNAPSHOT_DIR = ROOT / "data" / "snapshots" / "2026"
SEASON = 2026


def load(path, default):
    if not path.exists(): return default
    with path.open(encoding="utf-8") as f: return json.load(f)


def safe_float(value):
    try: return float(value)
    except (TypeError, ValueError): return None


def parse_dt(value):
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None
    except ValueError: return None


def is_fbs(game, side):
    return str(game.get(f"{side}Classification", "")).strip().lower() == "fbs"


def complete_score(game):
    home, away = safe_float(game.get("homePoints")), safe_float(game.get("awayPoints"))
    return None if home is None or away is None else (home, away)


def mean(values): return sum(values) / len(values) if values else None


def record(rows, key):
    results = [r.get(key) for r in rows if r.get(key) in {"W", "L", "P"}]
    return {"wins": results.count("W"), "losses": results.count("L"), "pushes": results.count("P"), "graded": len(results)}


def metrics(rows):
    if not rows:
        return {"games": 0, "winner_accuracy": None, "su_record": record([], "su_result"), "ats_record": record([], "ats_result"), "ou_record": record([], "ou_result"), "margin_mae": None, "margin_bias": None, "total_mae": None, "total_bias": None, "score_mae": None}
    winner = [1.0 if r["winner_correct"] else 0.0 for r in rows if r.get("winner_correct") is not None]
    margin = [r["margin_error"] for r in rows if r.get("margin_error") is not None]
    total = [r["total_error"] for r in rows if r.get("total_error") is not None]
    scores = [abs(r[k]) for r in rows for k in ("home_score_error", "away_score_error") if r.get(k) is not None]
    return {
        "games": len(rows), "winner_accuracy": mean(winner),
        "su_record": record(rows, "su_result"), "ats_record": record(rows, "ats_result"), "ou_record": record(rows, "ou_result"),
        "margin_mae": mean([abs(x) for x in margin]), "margin_bias": mean(margin),
        "total_mae": mean([abs(x) for x in total]), "total_bias": mean(total), "score_mae": mean(scores),
    }


def round_metrics(doc): return {k: round(v, 4) if isinstance(v, float) else v for k, v in doc.items()}


def closing_lines():
    archive = load(MARKET_ARCHIVE, {})
    out = {}
    for game_id, entry in archive.get("games", {}).items():
        start = parse_dt(entry.get("start_date"))
        snapshots = []
        for snap in entry.get("snapshots", []):
            captured = parse_dt(snap.get("captured_at"))
            if captured and (start is None or captured < start): snapshots.append((captured, snap))
        if not snapshots: continue
        _, snap = max(snapshots, key=lambda x: x[0])
        out[str(game_id)] = {
            "closing_spread": safe_float(snap.get("consensus_home_spread")),
            "closing_total": safe_float(snap.get("consensus_total")),
            "line_provider": "Project Gridiron consensus / The Odds API",
            "market_captured_at": snap.get("captured_at"),
            "spread_books": snap.get("spread_books"),
            "total_books": snap.get("total_books"),
        }
    print(f"Archived pre-kickoff closing-line games available: {len(out)}")
    return out


def apply_market_grade(row, market):
    if market:
        for key, value in market.items(): row[key] = value
    row["su_result"] = "W" if row.get("winner_correct") is True else "L" if row.get("winner_correct") is False else "P"
    close_spread, projected_margin, actual_margin = safe_float(row.get("closing_spread")), safe_float(row.get("projected_home_margin")), safe_float(row.get("actual_home_margin"))
    row["ats_pick"] = row["ats_result"] = row["ats_edge"] = None
    if close_spread is not None and projected_margin is not None and actual_margin is not None:
        edge = projected_margin - (-close_spread)
        row["ats_edge"] = round(abs(edge), 4)
        if abs(edge) > 1e-9:
            row["ats_pick"] = row.get("home_team") if edge > 0 else row.get("away_team")
            cover = actual_margin + close_spread
            if abs(cover) < 1e-9: row["ats_result"] = "P"
            elif (edge > 0 and cover > 0) or (edge < 0 and cover < 0): row["ats_result"] = "W"
            else: row["ats_result"] = "L"
    close_total, projected_total, actual_total = safe_float(row.get("closing_total")), safe_float(row.get("projected_total")), safe_float(row.get("actual_total"))
    row["ou_pick"] = row["ou_result"] = row["total_edge"] = None
    if close_total is not None and projected_total is not None and actual_total is not None:
        edge = projected_total - close_total
        row["total_edge"] = round(abs(edge), 4)
        if abs(edge) > 1e-9:
            row["ou_pick"] = "Over" if edge > 0 else "Under"
            if abs(actual_total - close_total) < 1e-9: row["ou_result"] = "P"
            elif (edge > 0 and actual_total > close_total) or (edge < 0 and actual_total < close_total): row["ou_result"] = "W"
            else: row["ou_result"] = "L"
    return row


def main():
    games = load(GAMES_FILE, [])
    published = load(PUBLISHED_PREDICTIONS, [])
    if isinstance(published, dict): published = published.get("predictions", published.get("games", []))
    previous = load(OUTPUT, {})
    previous_rows = list(previous.get("games", []))
    already = {str(r.get("game_id")) for r in previous_rows if r.get("game_id") is not None}
    games_by_id = {str(g.get("id")): g for g in games if isinstance(g, dict) and g.get("id") is not None and g.get("season") == SEASON}
    market_by_id = closing_lines()
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
        phm, pt = safe_float(pred.get("projected_home_margin")), safe_float(pred.get("projected_total"))
        phs = safe_float(pred.get("projected_home_score", pred.get("home_score")))
        pas = safe_float(pred.get("projected_away_score", pred.get("away_score")))
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
        row = {k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()}
        new_rows.append(apply_market_grade(row, market_by_id.get(str(game_id))))
    all_rows = [apply_market_grade(r, market_by_id.get(str(r.get("game_id")))) for r in previous_rows + new_rows]
    all_rows.sort(key=lambda r: (int(r.get("week") or 0), str(r.get("start_date") or ""), str(r.get("game_id") or "")))
    weeks = {}
    for row in all_rows: weeks.setdefault(str(row.get("week") if row.get("week") is not None else "unknown"), []).append(row)
    doc = {
        "season": SEASON, "generated_at": datetime.now(timezone.utc).isoformat(),
        "metric_notes": {
            "winner_accuracy": "share of games where projected straight-up winner matched actual winner",
            "su_record": "straight-up Project Gridiron winner record",
            "ats_record": "Project Gridiron side versus archived Project Gridiron consensus close; no pre-kickoff snapshot means no grade",
            "ou_record": "Project Gridiron O/U lean versus archived Project Gridiron consensus close; no pre-kickoff snapshot means no grade",
            "market_source": "The Odds API current NCAAF feed; median across available US books; final strictly pre-kickoff snapshot is official close",
            "margin_mae": "mean absolute error of projected home margin versus actual home margin",
            "total_mae": "mean absolute error of projected total versus actual total",
            "scope": "core performance ledger grades FBS-vs-FBS predictions only; FBS-vs-FCS projections are projection-only",
        },
        "cumulative": round_metrics(metrics(all_rows)), "by_week": {w: round_metrics(metrics(rows)) for w, rows in weeks.items()},
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
    print(f"Cumulative graded games: {len(all_rows)}"); print(f"ATS graded: {doc['cumulative']['ats_record']['graded']}"); print(f"O/U graded: {doc['cumulative']['ou_record']['graded']}")
    print(f"Saved to: {OUTPUT}")


if __name__ == "__main__": main()
