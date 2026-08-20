"""Export stable 2026 production JSON assets for GitHub Pages.

Usage:
    python3 -m data.export_site_2026
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "site_data"

RATINGS_FILE = PROCESSED / "preseason_ratings_v4_2026.json"
PREDICTIONS_FILE = PROCESSED / "game_predictions_2026.json"
RANKINGS_OUTPUT = SITE_DATA / "rankings_2026.json"
PREDICTIONS_OUTPUT = SITE_DATA / "game_predictions_2026.json"


def load(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    for path in (RATINGS_FILE, PREDICTIONS_FILE):
        if not path.exists():
            raise FileNotFoundError(f"Missing production site input: {path}")

    ratings = load(RATINGS_FILE)
    predictions = load(PREDICTIONS_FILE)

    ranked = sorted(ratings, key=lambda r: float(r.get("power_rating", 0.0)), reverse=True)
    ranking_rows = []

    for rank, row in enumerate(ranked, 1):
        features = row.get("preseason_features", {}) if isinstance(row, dict) else {}
        ranking_rows.append({
            "rank": rank,
            "team": row.get("team"),
            "power_rating": row.get("power_rating"),
            "preseason_v4_adjustment": row.get("preseason_v4_adjustment"),
            "returning_production": features.get("returning_production"),
            "transfer_talent": features.get("transfer_talent"),
            "qb_continuity": features.get("qb_continuity"),
            "coaching": features.get("coaching"),
        })

    SITE_DATA.mkdir(parents=True, exist_ok=True)

    with RANKINGS_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(ranking_rows, f, indent=2)

    with PREDICTIONS_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2)

    print("=" * 78)
    print("2026 PRODUCTION SITE EXPORT")
    print("=" * 78)
    print(f"Rankings exported: {len(ranking_rows)}")
    print(f"Game predictions exported: {len(predictions) if isinstance(predictions, list) else 0}")
    print(f"Saved: {RANKINGS_OUTPUT}")
    print(f"Saved: {PREDICTIONS_OUTPUT}")
    print("\nNext: commit and push site_data/ so GitHub Pages can serve the files.")


if __name__ == "__main__":
    main()
