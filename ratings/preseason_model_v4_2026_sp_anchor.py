"""Project Gridiron 2026 preseason V4 experiment using 2026 preseason SP+ as anchor.

Keeps the approved V4 offseason features, frozen weights, +/-6 cap, and the
2025 Project Gridiron offense/defense scores exactly as-is. The only change is
that the baseline SP+ season is 2026 instead of final 2025.

Usage:
    python -m ratings.preseason_model_v4_2026_sp_anchor
"""
import json
import math
from pathlib import Path

from ratings.preseason_model_v4_config import PRESEASON_V4_MAX_ADJUSTMENT, PRESEASON_V4_WEIGHTS

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "data" / "processed"
FILES = {
    "sp": ROOT / "data" / "raw" / "sp_ratings" / "2026.json",
    "gridiron": P / "power_ratings_2025.json",
    "rp": P / "returning_production_2026.json",
    "tt": P / "transfer_talent_2026.json",
    "qb": P / "qb_continuity_2026.json",
    "coach": P / "coaching_continuity_v2_2026.json",
}
CURRENT = P / "preseason_ratings_v4_2026.json"
OUTPUT = P / "preseason_ratings_v4_2026_sp_anchor.json"
COMPARE = P / "preseason_2026_anchor_comparison.json"
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


def extract_rp(r): return get(r, "overall", "percent", default=get(r, "returning_percentage"))
def extract_tt(r): return get(r, "net", "high_end_count")
def extract_qb(r): return get(r, "continuity_score")
def extract_coach(r): return get(r, "change_after_losing_season")


def main():
    missing = [p for p in FILES.values() if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing inputs: " + ", ".join(str(p) for p in missing))

    data = {k: lookup(load(p)) for k, p in FILES.items()}
    teams = sorted(set(data["sp"]) & set(data["gridiron"]))
    sp_vals = [get(data["sp"][t], "rating") for t in teams]
    g_vals = [get(data["gridiron"][t], "power_rating") for t in teams]
    sp_mean, sp_std = avg(sp_vals), sd(sp_vals)
    g_mean, g_std = avg(g_vals), sd(g_vals)

    rows = []
    for team in teams:
        g = data["gridiron"][team]
        baseline = g_mean + z(get(data["sp"][team], "rating"), sp_mean, sp_std) * g_std
        rows.append({
            "team": team,
            "baseline": baseline,
            "offense_score": get(g, "offense_score"),
            "defense_score": get(g, "defense_score"),
            "returning_production": extract_rp(data["rp"].get(team, {})),
            "transfer_talent": extract_tt(data["tt"].get(team, {})),
            "qb_continuity": extract_qb(data["qb"].get(team, {})),
            "coaching": extract_coach(data["coach"].get(team, {})),
        })

    ctx = {k: {"mean": avg([r[k] for r in rows]), "std": sd([r[k] for r in rows])} for k in FEATURES}
    output = []
    for r in rows:
        parts = {k: z(r[k], ctx[k]["mean"], ctx[k]["std"]) * PRESEASON_V4_WEIGHTS[k] for k in FEATURES}
        parts["transfer_production"] = 0.0
        raw_adj = sum(parts.values())
        adj = max(-PRESEASON_V4_MAX_ADJUSTMENT, min(PRESEASON_V4_MAX_ADJUSTMENT, raw_adj))
        output.append({
            "season": 2026,
            "team": r["team"],
            "power_rating": round(r["baseline"] + adj, 4),
            "baseline_sp_mapped": round(r["baseline"], 4),
            "baseline_sp_season": 2026,
            "preseason_v4_adjustment": round(adj, 4),
            "offense_score": r["offense_score"],
            "defense_score": r["defense_score"],
            "adjustment_parts": {k: round(v, 4) for k, v in parts.items()},
            "preseason_features": {k: r[k] for k in FEATURES},
            "returning_production_source": "2026 returning_snap_percent proxy",
            "model_version": "preseason_v4_2026_sp_anchor_experiment",
        })

    output.sort(key=lambda r: r["power_rating"], reverse=True)
    for i, row in enumerate(output, 1): row["rank"] = i
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=4), encoding="utf-8")

    current = lookup(load(CURRENT)) if CURRENT.exists() else {}
    comparison = []
    for row in output:
        old = current.get(row["team"], {})
        old_rating = sf(old.get("power_rating"), None)
        comparison.append({
            "team": row["team"],
            "current_2025_sp_anchor": old_rating,
            "new_2026_sp_anchor": row["power_rating"],
            "change": round(row["power_rating"] - old_rating, 4) if old_rating is not None else None,
            "new_rank": row["rank"],
        })
    comparison.sort(key=lambda r: abs(r["change"]) if r["change"] is not None else -1, reverse=True)
    COMPARE.write_text(json.dumps({"teams": len(output), "comparison": comparison}, indent=4), encoding="utf-8")

    print("=" * 78)
    print("2026 PRESEASON V4 - SAME-SEASON SP+ ANCHOR EXPERIMENT")
    print("=" * 78)
    print(f"Teams rated: {len(output)}")
    print("Only changed input: final 2025 SP+ anchor -> preseason 2026 SP+ anchor")
    print("All V4 weights, cap, features, offense/defense scores remain unchanged.")
    print("\nTOP 25")
    print("-" * 78)
    for row in output[:25]:
        print(f"{row['rank']:>2}. {row['team']}: {row['power_rating']:+.2f} ({row['preseason_v4_adjustment']:+.2f} V4 adj)")
    print("\nBIGGEST CHANGES VS CURRENT MODEL")
    print("-" * 78)
    for row in comparison[:25]:
        if row["change"] is not None:
            print(f"{row['team']}: {row['current_2025_sp_anchor']:+.2f} -> {row['new_2026_sp_anchor']:+.2f} ({row['change']:+.2f})")
    print(f"\nSaved: {OUTPUT}")
    print(f"Comparison: {COMPARE}")


if __name__ == "__main__": main()
