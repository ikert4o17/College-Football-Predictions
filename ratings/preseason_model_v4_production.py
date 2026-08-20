"""Project Gridiron 2026 preseason model V4 production runner.

Uses the same baseline construction as the validated V4 model:
2025 SP+ mapped onto the 2025 Project Gridiron rating scale, followed by the
frozen multi-year preseason adjustments.

Important: CFBD's 2026 returning-production source now supplies returning snap
percentage rather than the historical returning-PPA percentage. Because the V4
feature is standardized within season, this is usable as a preseason proxy, but
it is explicitly marked as a schema/proxy change in the output and should be
revalidated once another season is available.

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
    "sp": ROOT / "data" / "raw" / "sp_ratings" / "2025.json",
    "gridiron": P / "power_ratings_2025.json",
    "rp": P / "returning_production_2026.json",
    "tt": P / "transfer_talent_2026.json",
    "qb": P / "qb_continuity_2026.json",
    "coach": P / "coaching_continuity_v2_2026.json",
}
OUTPUT = P / "preseason_ratings_v4_2026.json"
FEATURES = ["returning_production", "transfer_talent", "qb_continuity", "coaching"]


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


def mapped_sp_baseline(team, sp, gridiron, sp_mean, sp_std, g_mean, g_std):
    return g_mean + z(get(sp[team], "rating"), sp_mean, sp_std) * g_std


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
    sp = data["sp"]
    gridiron = data["gridiron"]
    teams = sorted(set(sp) & set(gridiron))

    sp_values = [get(sp[t], "rating") for t in teams]
    g_values = [get(gridiron[t], "power_rating") for t in teams]
    sp_mean, sp_std = avg(sp_values), sd(sp_values)
    g_mean, g_std = avg(g_values), sd(g_values)

    rows = []
    for team in teams:
        g = gridiron[team]
        rows.append({
            "team": team,
            "baseline": mapped_sp_baseline(team, sp, gridiron, sp_mean, sp_std, g_mean, g_std),
            "offense_score": get(g, "offense_score"),
            "defense_score": get(g, "defense_score"),
            "returning_production": extract_rp(data["rp"].get(team, {})),
            "transfer_talent": extract_tt(data["tt"].get(team, {})),
            "qb_continuity": extract_qb(data["qb"].get(team, {})),
            "coaching": extract_coach(data["coach"].get(team, {})),
        })

    ctx = {
        k: {"mean": avg([r[k] for r in rows]), "std": sd([r[k] for r in rows]),
            "min": min(r[k] for r in rows), "max": max(r[k] for r in rows)}
        for k in FEATURES
    }

    output = []
    capped = 0
    for r in rows:
        parts = {
            k: z(r[k], ctx[k]["mean"], ctx[k]["std"]) * PRESEASON_V4_WEIGHTS[k]
            for k in FEATURES
        }
        parts["transfer_production"] = 0.0
        raw_adj = sum(parts.values())
        adj = max(-PRESEASON_V4_MAX_ADJUSTMENT, min(PRESEASON_V4_MAX_ADJUSTMENT, raw_adj))
        if abs(raw_adj) > PRESEASON_V4_MAX_ADJUSTMENT:
            capped += 1
        rating = r["baseline"] + adj
        output.append({
            "season": 2026,
            "team": r["team"],
            "power_rating": round(rating, 4),
            "baseline_sp_mapped": round(r["baseline"], 4),
            "preseason_v4_adjustment": round(adj, 4),
            "offense_score": r["offense_score"],
            "defense_score": r["defense_score"],
            "adjustment_parts": {k: round(v, 4) for k, v in parts.items()},
            "preseason_features": {k: r[k] for k in FEATURES},
            "returning_production_source": "2026 returning_snap_percent proxy",
        })

    output.sort(key=lambda r: r["power_rating"], reverse=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)

    print(f"\nTeams rated: {len(output)}")
    print("Baseline: 2025 SP+ mapped to 2025 Project Gridiron scale")
    print("Returning production: 2026 returning-snap percentage proxy")
    print("Frozen weights:")
    for k, v in PRESEASON_V4_WEIGHTS.items():
        print(f"  {k}: {v:+.2f} pts/std")
    print(f"Adjustment cap: +/-{PRESEASON_V4_MAX_ADJUSTMENT:.1f}")
    print(f"Teams reaching adjustment cap: {capped}")

    print("\nFEATURE DISTRIBUTIONS")
    print("-" * 78)
    for k in FEATURES:
        c = ctx[k]
        print(f"{k}: mean={c['mean']:.4f}, std={c['std']:.4f}, min={c['min']:.4f}, max={c['max']:.4f}")

    print("\nTOP 25 2026 PRESEASON V4 RATINGS")
    print("-" * 78)
    for i, r in enumerate(output[:25], 1):
        print(f"{i:>2}. {r['team']}: {r['power_rating']:+.2f} ({r['preseason_v4_adjustment']:+.2f} adjustment)")

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
