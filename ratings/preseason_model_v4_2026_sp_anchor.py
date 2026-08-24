"""Project Gridiron 2026 preseason V4 experiment using 2026 preseason SP+ as anchor.

Keeps the approved V4 offseason features, frozen weights, +/-6 cap, and the
2025 Project Gridiron offense/defense scores exactly as-is. The only change is
that the baseline SP+ season is 2026 instead of final 2025.

The canonical 2026 V4 feature values are read from the published site_data
rankings. This makes the GitHub experiment self-contained even when locally
produced intermediate JSON files are not tracked in the repository.

Usage:
    python -m ratings.preseason_model_v4_2026_sp_anchor
"""
import json
import math
from pathlib import Path

from ratings.preseason_model_v4_config import PRESEASON_V4_MAX_ADJUSTMENT, PRESEASON_V4_WEIGHTS

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "data" / "processed"
SP_FILE = ROOT / "data" / "raw" / "sp_ratings" / "2026.json"
GRIDIRON_FILE = P / "power_ratings_2025.json"
RANKINGS_MANIFEST = ROOT / "site_data" / "rankings_2026.json"
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


def load_published_rankings():
    """Load the canonical published 2026 V4 rankings, including multipart data."""
    if not RANKINGS_MANIFEST.exists():
        raise FileNotFoundError(f"Published rankings manifest missing: {RANKINGS_MANIFEST}")

    manifest = load(RANKINGS_MANIFEST)
    if isinstance(manifest, list):
        return manifest
    if isinstance(manifest, dict) and isinstance(manifest.get("rankings"), list):
        return manifest["rankings"]
    if isinstance(manifest, dict) and isinstance(manifest.get("parts"), list):
        rows = []
        for relative in manifest["parts"]:
            path = ROOT / relative
            if not path.exists():
                raise FileNotFoundError(f"Published rankings part missing: {path}")
            part = load(path)
            if not isinstance(part, list):
                raise ValueError(f"Published rankings part is not a list: {path}")
            rows.extend(part)
        return rows
    raise ValueError("Unsupported site_data/rankings_2026.json format")


def main():
    missing = [p for p in (SP_FILE, GRIDIRON_FILE, RANKINGS_MANIFEST) if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing inputs: " + ", ".join(str(p) for p in missing))

    sp = lookup(load(SP_FILE))
    gridiron = lookup(load(GRIDIRON_FILE))
    published = lookup(load_published_rankings())

    teams = sorted(set(sp) & set(gridiron) & set(published))
    if not teams:
        raise ValueError("No common teams across 2026 SP+, 2025 Gridiron, and published 2026 V4 data.")

    sp_vals = [get(sp[t], "rating") for t in teams]
    g_vals = [get(gridiron[t], "power_rating") for t in teams]
    sp_mean, sp_std = avg(sp_vals), sd(sp_vals)
    g_mean, g_std = avg(g_vals), sd(g_vals)

    rows = []
    for team in teams:
        g = gridiron[team]
        pub = published[team]
        baseline = g_mean + z(get(sp[team], "rating"), sp_mean, sp_std) * g_std
        rows.append({
            "team": team,
            "baseline": baseline,
            "offense_score": get(g, "offense_score"),
            "defense_score": get(g, "defense_score"),
            "returning_production": get(pub, "returning_production"),
            "transfer_talent": get(pub, "transfer_talent"),
            "qb_continuity": get(pub, "qb_continuity"),
            "coaching": get(pub, "coaching"),
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
            "feature_source": "published site_data/rankings_2026",
            "model_version": "preseason_v4_2026_sp_anchor_experiment",
        })

    output.sort(key=lambda r: r["power_rating"], reverse=True)
    for i, row in enumerate(output, 1):
        row["rank"] = i
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=4), encoding="utf-8")

    comparison = []
    for row in output:
        old = published.get(row["team"], {})
        old_rating = sf(old.get("power_rating"), None)
        old_rank = old.get("rank")
        comparison.append({
            "team": row["team"],
            "current_2025_sp_anchor": old_rating,
            "current_rank": old_rank,
            "new_2026_sp_anchor": row["power_rating"],
            "change": round(row["power_rating"] - old_rating, 4) if old_rating is not None else None,
            "new_rank": row["rank"],
            "rank_change": (int(old_rank) - row["rank"]) if old_rank is not None else None,
        })
    comparison.sort(key=lambda r: abs(r["change"]) if r["change"] is not None else -1, reverse=True)
    COMPARE.write_text(json.dumps({
        "teams": len(output),
        "old_anchor": "final 2025 SP+ mapped to 2025 Project Gridiron scale",
        "new_anchor": "preseason 2026 SP+ mapped to 2025 Project Gridiron scale",
        "all_other_v4_inputs_unchanged": True,
        "comparison": comparison,
    }, indent=4), encoding="utf-8")

    print("=" * 78)
    print("2026 PRESEASON V4 - SAME-SEASON SP+ ANCHOR EXPERIMENT")
    print("=" * 78)
    print(f"Teams rated: {len(output)}")
    print("Only changed input: final 2025 SP+ anchor -> preseason 2026 SP+ anchor")
    print("All V4 weights, cap, features, offense/defense scores remain unchanged.")
    print("Canonical V4 feature values loaded from published site_data rankings.")
    print("\nTOP 25")
    print("-" * 78)
    for row in output[:25]:
        print(f"{row['rank']:>2}. {row['team']}: {row['power_rating']:+.2f} ({row['preseason_v4_adjustment']:+.2f} V4 adj)")
    print("\nBIGGEST CHANGES VS CURRENT MODEL")
    print("-" * 78)
    for row in comparison[:25]:
        if row["change"] is not None:
            rank_note = "" if row["rank_change"] is None else f", rank {row['current_rank']} -> {row['new_rank']}"
            print(f"{row['team']}: {row['current_2025_sp_anchor']:+.2f} -> {row['new_2026_sp_anchor']:+.2f} ({row['change']:+.2f}{rank_note})")
    print(f"\nSaved: {OUTPUT}")
    print(f"Comparison: {COMPARE}")


if __name__ == "__main__":
    main()
