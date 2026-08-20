"""Project Gridiron 2026 preseason model V4 production runner.

Applies the frozen multi-year V4 weights to the 2025 Project Gridiron power
rating baseline and the available 2026 preseason features.

Usage:
    python3 -m ratings.preseason_model_v4_production
"""
import json
import math
from pathlib import Path

from ratings.preseason_model_v4_config import (
    PRESEASON_V4_MAX_ADJUSTMENT,
    PRESEASON_V4_WEIGHTS,
)

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "data" / "processed"
FILES = {
    "baseline": P / "power_ratings_2025.json",
    "rp": P / "returning_production_2026.json",
    "tt": P / "transfer_talent_2026.json",
    "qb": P / "qb_continuity_2026.json",
    "coach": P / "coaching_continuity_v2_2026.json",
}
OUTPUT = P / "preseason_ratings_v4_2026.json"


def load(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def lookup(records):
    return {r["team"]: r for r in records if isinstance(r, dict) and r.get("team")}


def sf(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def get(r, *keys, default=0.0):
    v = r
    for k in keys:
        if not isinstance(v, dict) or k not in v or v[k] is None:
            return default
        v = v[k]
    return sf(v, default)


def avg(xs):
    return sum(xs) / len(xs) if xs else 0.0


def sd(xs):
    if not xs:
        return 0.0
    m = avg(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def z(x, m, s):
    return (x - m) / s if s else 0.0


def extract_rp(r):
    return get(r, "overall", "percent", default=get(r, "returning_percentage"))


def extract_tt(r):
    return get(r, "net", "high_end_count")


def extract_qb(r):
    return get(r, "continuity_score")


def extract_coach(r):
    return get(r, "change_after_losing_season")


def main():
    print("=" * 78)
    print("PROJECT GRIDIRON 2026 PRESEASON MODEL V4 - PRODUCTION")
    print("=" * 78)

    missing = [p for p in FILES.values() if not p.exists()]
    if missing:
        print("\nMISSING INPUTS")
        print("-" * 78)
        for p in missing:
            print(p)
        raise FileNotFoundError("2026 preseason V4 production inputs are incomplete.")

    data = {k: lookup(load(p)) for k, p in FILES.items()}
    baseline = data["baseline"]

    rows = []
    for team in sorted(baseline):
        b = baseline[team]
        rows.append({
            "team": team,
            "baseline_2025": get(b, "power_rating"),
            "offense_score": get(b, "offense_score"),
            "defense_score": get(b, "defense_score"),
            "returning_production": extract_rp(data["rp"].get(team, {})),
            "transfer_talent": extract_tt(data["tt"].get(team, {})),
            "qb_continuity": extract_qb(data["qb"].get(team, {})),
            "coaching": extract_coach(data["coach"].get(team, {})),
        })

    features = ["returning_production", "transfer_talent", "qb_continuity", "coaching"]
    ctx = {
        k: {"mean": avg([r[k] for r in rows]), "std": sd([r[k] for r in rows])}
        for k in features
    }

    output = []
    for r in rows:
        parts = {
            k: z(r[k], ctx[k]["mean"], ctx[k]["std"]) * PRESEASON_V4_WEIGHTS[k]
            for k in features
        }
        # Transfer production is intentionally frozen at zero in V4 production.
        parts["transfer_production"] = 0.0
        raw_adj = sum(parts.values())
        adj = max(-PRESEASON_V4_MAX_ADJUSTMENT, min(PRESEASON_V4_MAX_ADJUSTMENT, raw_adj))
        rating = r["baseline_2025"] + adj
        output.append({
            "season": 2026,
            "team": r["team"],
            "power_rating": round(rating, 4),
            "baseline_2025": round(r["baseline_2025"], 4),
            "preseason_v4_adjustment": round(adj, 4),
            "offense_score": r["offense_score"],
            "defense_score": r["defense_score"],
            "adjustment_parts": {k: round(v, 4) for k, v in parts.items()},
            "preseason_features": {k: r[k] for k in features},
        })

    output.sort(key=lambda r: r["power_rating"], reverse=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)

    print(f"\nTeams rated: {len(output)}")
    print("Frozen weights:")
    for k, v in PRESEASON_V4_WEIGHTS.items():
        print(f"  {k}: {v:+.2f} pts/std")
    print(f"Adjustment cap: +/-{PRESEASON_V4_MAX_ADJUSTMENT:.1f}")

    print("\nTOP 25 2026 PRESEASON V4 RATINGS")
    print("-" * 78)
    for i, r in enumerate(output[:25], 1):
        print(f"{i:>2}. {r['team']}: {r['power_rating']:+.2f} ({r['preseason_v4_adjustment']:+.2f} vs 2025)")

    print("\nBIGGEST POSITIVE ADJUSTMENTS")
    print("-" * 78)
    for r in sorted(output, key=lambda x: x["preseason_v4_adjustment"], reverse=True)[:15]:
        print(f"{r['team']}: {r['preseason_v4_adjustment']:+.2f}")

    print("\nBIGGEST NEGATIVE ADJUSTMENTS")
    print("-" * 78)
    for r in sorted(output, key=lambda x: x["preseason_v4_adjustment"])[:15]:
        print(f"{r['team']}: {r['preseason_v4_adjustment']:+.2f}")

    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
