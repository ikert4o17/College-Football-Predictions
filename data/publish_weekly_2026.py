"""Publish current 2026 ratings and predictions to GitHub Pages site_data.

This is the final packaging step of the weekly operating system. It only runs
after ratings and predictions have been generated successfully.
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RATINGS = ROOT / "data" / "processed" / "inseason_ratings_2026.json"
PREDICTIONS = ROOT / "data" / "processed" / "game_predictions_2026.json"
STATE = ROOT / "data" / "processed" / "weekly_state_2026.json"
SITE = ROOT / "site_data"
SNAPSHOT_DIR = ROOT / "data" / "snapshots" / "2026"
CHUNK_SIZE = 40


def load(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main():
    for path in (RATINGS, PREDICTIONS, STATE):
        if not path.exists():
            raise FileNotFoundError(path)

    rating_data = load(RATINGS)
    ratings = rating_data.get("ratings", rating_data if isinstance(rating_data, list) else [])
    predictions_data = load(PREDICTIONS)
    predictions = (
        predictions_data
        if isinstance(predictions_data, list)
        else predictions_data.get("predictions", [])
    )
    state = load(STATE)

    if len(ratings) < 130:
        raise ValueError(f"Refusing to publish incomplete rankings: {len(ratings)} teams")

    SITE.mkdir(parents=True, exist_ok=True)
    compact = []
    for row in ratings:
        compact.append({
            "rank": row.get("rank"),
            "team": row.get("team"),
            "power_rating": row.get("power_rating"),
            "preseason_power_rating": row.get("preseason_power_rating"),
            "inseason_adjustment": row.get("inseason_adjustment", 0.0),
            "games_inseason": row.get("games_inseason", 0),
            "returning_production": row.get("returning_production", 0.0),
            "transfer_talent": row.get("transfer_talent", 0.0),
            "qb_continuity": row.get("qb_continuity", 0.0),
            "coaching": row.get("coaching", 0.0),
            "model_version": row.get("model_version"),
        })

    part_paths = []
    for i in range(0, len(compact), CHUNK_SIZE):
        part_number = i // CHUNK_SIZE + 1
        path = SITE / f"rankings_2026_part{part_number}.json"
        path.write_text(json.dumps(compact[i:i + CHUNK_SIZE], indent=2), encoding="utf-8")
        part_paths.append(str(path.relative_to(ROOT)))

    # Remove stale extra parts if chunk count ever shrinks.
    valid_names = {Path(p).name for p in part_paths}
    for path in SITE.glob("rankings_2026_part*.json"):
        if path.name not in valid_names:
            path.unlink()

    manifest = {
        "season": 2026,
        "model_version": rating_data.get("model_version", "2026_inseason_v1_balanced_light_prior"),
        "latest_completed_week": state.get("latest_completed_week"),
        "teams": len(compact),
        "parts": part_paths,
    }
    (SITE / "rankings_2026.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (SITE / "game_predictions_2026.json").write_text(json.dumps(predictions, indent=2), encoding="utf-8")

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    upcoming_weeks = sorted({p.get("week") for p in predictions if p.get("week") is not None})
    if upcoming_weeks:
        target = upcoming_weeks[0]
        pred_snapshot = SNAPSHOT_DIR / f"predictions_week_{int(target):02d}.json"
        if not pred_snapshot.exists():
            pred_snapshot.write_text(json.dumps(predictions, indent=2), encoding="utf-8")

    print("=" * 78)
    print("PROJECT GRIDIRON 2026 SITE PUBLISH PACKAGE")
    print("=" * 78)
    print(f"Rankings published: {len(compact)}")
    print(f"Predictions published: {len(predictions)}")
    print(f"Ranking parts: {len(part_paths)}")
    print(f"Latest completed week: {state.get('latest_completed_week')}")


if __name__ == "__main__":
    main()
