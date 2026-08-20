"""Audit capped 2026 Project Gridiron preseason V4 adjustments.

Usage:
    python3 -m ratings.audit_preseason_v4_caps
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "processed" / "preseason_ratings_v4_2026.json"
CAP = 6.0
EPS = 1e-6


def main():
    with INPUT.open(encoding="utf-8") as f:
        rows = json.load(f)

    capped = [r for r in rows if abs(float(r.get("preseason_v4_adjustment", 0.0))) >= CAP - EPS]
    capped.sort(key=lambda r: (-float(r.get("preseason_v4_adjustment", 0.0)), r.get("team", "")))

    print("=" * 78)
    print("2026 PRESEASON V4 ADJUSTMENT-CAP AUDIT")
    print("=" * 78)
    print(f"\nTeams rated: {len(rows)}")
    print(f"Teams at +/-{CAP:.1f} cap: {len(capped)}")

    for r in capped:
        print("\n" + r["team"])
        print("-" * 78)
        print(f"Baseline: {float(r.get('baseline_2025', 0.0)):+.2f}")
        print(f"Final rating: {float(r.get('power_rating', 0.0)):+.2f}")
        print(f"Capped adjustment: {float(r.get('preseason_v4_adjustment', 0.0)):+.2f}")

        parts = r.get("adjustment_parts", {})
        raw = sum(float(v or 0.0) for v in parts.values())
        print(f"Raw adjustment before cap: {raw:+.2f}")
        print("Components:")
        for key in ["returning_production", "transfer_talent", "transfer_production", "qb_continuity", "coaching"]:
            print(f"  {key}: {float(parts.get(key, 0.0) or 0.0):+.2f}")

        features = r.get("preseason_features", {})
        print("Raw feature values:")
        for key in ["returning_production", "transfer_talent", "qb_continuity", "coaching"]:
            value = features.get(key)
            if isinstance(value, (int, float)):
                print(f"  {key}: {value:+.4f}")
            else:
                print(f"  {key}: {value}")

    print("\n" + "=" * 78)
    print("AUDIT COMPLETE")
    print("=" * 78)


if __name__ == "__main__":
    main()
