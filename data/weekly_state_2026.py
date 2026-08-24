"""Create the authoritative Project Gridiron weekly season state for 2026.

The state is derived from refreshed CFBD games plus the current in-season rating
artifact. It records the latest completed week, applied game IDs, and snapshot
paths so the weekly workflow is auditable and reproducible.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAMES = ROOT / "data" / "raw" / "games.json"
RATINGS = ROOT / "data" / "processed" / "inseason_ratings_2026.json"
STATE = ROOT / "data" / "processed" / "weekly_state_2026.json"
SNAPSHOT_DIR = ROOT / "data" / "snapshots" / "2026"


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


def is_completed_fbs(game):
    if not isinstance(game, dict) or game.get("season") != 2026:
        return False
    if game.get("seasonType") != "regular":
        return False
    if str(game.get("homeClassification", "")).lower() != "fbs":
        return False
    if str(game.get("awayClassification", "")).lower() != "fbs":
        return False
    if game.get("homePoints") is None or game.get("awayPoints") is None:
        return False
    dt = parse_date(game.get("startDate"))
    return dt is not None and dt < datetime.now(timezone.utc)


def week_value(game):
    try:
        return int(game.get("week"))
    except (TypeError, ValueError):
        return 0


def main():
    if not GAMES.exists():
        raise FileNotFoundError(GAMES)
    if not RATINGS.exists():
        raise FileNotFoundError(RATINGS)

    games = load(GAMES)
    rating_data = load(RATINGS)
    completed = sorted(
        [g for g in games if is_completed_fbs(g)],
        key=lambda g: (week_value(g), g.get("startDate") or "", str(g.get("id") or "")),
    )
    latest_week = max((week_value(g) for g in completed), default=-1)
    applied_ids = [str(g.get("id")) for g in completed if g.get("id") is not None]

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    label = "preseason" if latest_week < 0 else f"after_week_{latest_week:02d}"
    rating_snapshot = SNAPSHOT_DIR / f"ratings_{label}.json"
    if not rating_snapshot.exists():
        rating_snapshot.write_text(json.dumps(rating_data, indent=4), encoding="utf-8")

    state = {
        "season": 2026,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_completed_week": latest_week,
        "completed_fbs_vs_fbs_games": len(completed),
        "applied_game_ids": applied_ids,
        "rating_snapshot": str(rating_snapshot.relative_to(ROOT)),
        "current_ratings": str(RATINGS.relative_to(ROOT)),
        "rebuild_strategy": "always rebuild from frozen preseason and all completed games",
    }
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=4), encoding="utf-8")

    print("=" * 78)
    print("PROJECT GRIDIRON 2026 WEEKLY STATE")
    print("=" * 78)
    print(f"Latest completed week: {latest_week}")
    print(f"Completed FBS-vs-FBS games: {len(completed)}")
    print(f"Rating snapshot: {rating_snapshot}")
    print(f"State: {STATE}")


if __name__ == "__main__":
    main()
