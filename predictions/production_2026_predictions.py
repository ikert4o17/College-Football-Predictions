"""Project Gridiron 2026 production game predictions.

Promotes the approved preseason V4 ratings into the existing calibrated 2026
prediction pipeline while preserving the older provisional ratings/predictions.

Usage:
    python3 -m predictions.production_2026_predictions
"""
import json
from pathlib import Path

from predictions import provisional_2026_predictions as pipeline

ROOT = Path(__file__).resolve().parent.parent
RATINGS_FILE = ROOT / "data" / "processed" / "preseason_ratings_v4_2026.json"
OUTPUT_FILE = ROOT / "data" / "processed" / "game_predictions_2026.json"


def main():
    if not RATINGS_FILE.exists():
        raise FileNotFoundError(
            f"Approved 2026 preseason V4 ratings missing: {RATINGS_FILE}"
        )

    # Reuse the already-calibrated 2026 margin/total pipeline, changing only
    # the rating source and output destination. The provisional artifacts stay
    # untouched for historical comparison.
    pipeline.RATINGS_FILE = RATINGS_FILE
    pipeline.OUTPUT_FILE = OUTPUT_FILE
    pipeline.main()

    with OUTPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    records = data if isinstance(data, list) else data.get("predictions", [])
    for record in records:
        if not isinstance(record, dict):
            continue
        record["provisional"] = False
        record["rating_model"] = "preseason_v4_2026_production"

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print("\n2026 PRODUCTION PROMOTION COMPLETE")
    print("-" * 78)
    print(f"Rating source: {RATINGS_FILE}")
    print(f"Production predictions: {OUTPUT_FILE}")
    print("Legacy power_ratings_2026.json and provisional predictions preserved.")


if __name__ == "__main__":
    main()
