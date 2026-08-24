"""Generate upcoming 2026 predictions from current in-season ratings."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from predictions import provisional_2026_predictions as base

ROOT = Path(__file__).resolve().parent.parent
RATINGS = ROOT / "data" / "processed" / "inseason_ratings_2026.json"
GAMES = ROOT / "data" / "raw" / "games.json"
OUTPUT = ROOT / "data" / "processed" / "game_predictions_2026.json"
LOOKAHEAD_DAYS = 8


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


def is_fbs(game, side):
    return str(game.get(f"{side}Classification", "")).strip().lower() == "fbs"


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
    predictions = []
    skipped_missing = 0

    for game in games:
        if not isinstance(game, dict) or game.get("season") != 2026:
            continue
        if game.get("seasonType") != "regular":
            continue
        start = parse_date(game.get("startDate"))
        if start is None or start < now or start > end:
            continue
        if not (is_fbs(game, "home") and is_fbs(game, "away")):
            continue

        projection = base.project_game(game, rating_lookup, margin, total)
        if projection is None:
            skipped_missing += 1
            continue
        projection["provisional"] = False
        projection["rating_model"] = "2026_inseason_v1"
        predictions.append(projection)

    predictions.sort(key=lambda r: r.get("start_date") or "")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=4)

    print("=" * 78)
    print("PROJECT GRIDIRON 2026 WEEKLY PREDICTIONS")
    print("=" * 78)
    print(f"Window: {now.isoformat()} through {end.isoformat()}")
    print(f"Ratings loaded: {len(rating_lookup)}")
    print(f"Predictions generated: {len(predictions)}")
    print(f"Upcoming FBS games skipped for missing rating data: {skipped_missing}")
    print(f"Saved to: {OUTPUT}")
    print("\nUPCOMING PROJECTIONS")
    print("-" * 78)
    for row in predictions:
        print(f"{row['away_team']} @ {row['home_team']}: {row['projected_winner']} by {row['projected_margin']:.1f}, total {row['projected_total']:.1f}")


if __name__ == "__main__":
    main()
