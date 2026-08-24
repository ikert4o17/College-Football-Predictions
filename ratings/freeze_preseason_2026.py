"""Build the canonical frozen 2026 Project Gridiron preseason ratings.

Anchor: 2026 preseason SP+ mapped to the 2025 Project Gridiron scale.
Overlay: Balanced Light (frozen in ratings.preseason_2026_config).
"""
import json
import math
from pathlib import Path

from ratings.preseason_2026_config import (
    PRESEASON_2026_ANCHOR,
    PRESEASON_2026_MAX_ADJUSTMENT,
    PRESEASON_2026_MODEL_VERSION,
    PRESEASON_2026_WEIGHTS,
)

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "data" / "processed"
SP_FILE = ROOT / "data" / "raw" / "sp_ratings" / "2026.json"
GRIDIRON_FILE = P / "power_ratings_2025.json"
RANKINGS_MANIFEST = ROOT / "site_data" / "rankings_2026.json"
OUTPUT = P / "preseason_ratings_2026.json"
FEATURES = list(PRESEASON_2026_WEIGHTS)


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
    manifest = load(RANKINGS_MANIFEST)
    if isinstance(manifest, list):
        return manifest
    if isinstance(manifest, dict) and isinstance(manifest.get("rankings"), list):
        return manifest["rankings"]
    if isinstance(manifest, dict) and isinstance(manifest.get("parts"), list):
        rows = []
        for relative in manifest["parts"]:
            rows.extend(load(ROOT / relative))
        return rows
    raise ValueError("Unsupported rankings manifest format")


def main():
    for path in (SP_FILE, GRIDIRON_FILE, RANKINGS_MANIFEST):
        if not path.exists():
            raise FileNotFoundError(path)

    sp = lookup(load(SP_FILE))
    prior = lookup(load(GRIDIRON_FILE))
    published = lookup(load_published_rankings())
    teams = sorted(set(sp) & set(prior) & set(published))
    if not teams:
        raise ValueError("No common teams for frozen preseason ratings")

    sp_vals = [get(sp[t], "rating") for t in teams]
    prior_vals = [get(prior[t], "power_rating") for t in teams]
    sp_mean, sp_std = avg(sp_vals), sd(sp_vals)
    prior_mean, prior_std = avg(prior_vals), sd(prior_vals)

    base_rows = []
    for team in teams:
        p = prior[team]
        pub = published[team]
        baseline = prior_mean + z(get(sp[team], "rating"), sp_mean, sp_std) * prior_std
        base_rows.append({
            "team": team,
            "baseline": baseline,
            "offense_score": get(p, "offense_score"),
            "defense_score": get(p, "defense_score"),
            **{feature: get(pub, feature) for feature in FEATURES},
        })

    ctx = {
        feature: {
            "mean": avg([row[feature] for row in base_rows]),
            "std": sd([row[feature] for row in base_rows]),
        }
        for feature in FEATURES
    }

    output = []
    for row in base_rows:
        parts = {
            feature: z(row[feature], ctx[feature]["mean"], ctx[feature]["std"])
            * PRESEASON_2026_WEIGHTS[feature]
            for feature in FEATURES
        }
        raw = sum(parts.values())
        adj = max(-PRESEASON_2026_MAX_ADJUSTMENT, min(PRESEASON_2026_MAX_ADJUSTMENT, raw))
        output.append({
            "season": 2026,
            "team": row["team"],
            "power_rating": round(row["baseline"] + adj, 4),
            "baseline_sp_mapped": round(row["baseline"], 4),
            "baseline_sp_season": 2026,
            "preseason_adjustment": round(adj, 4),
            "preseason_v4_adjustment": round(adj, 4),
            "offense_score": row["offense_score"],
            "defense_score": row["defense_score"],
            "returning_production": row["returning_production"],
            "transfer_talent": row["transfer_talent"],
            "qb_continuity": row["qb_continuity"],
            "coaching": row["coaching"],
            "adjustment_parts": {k: round(v, 4) for k, v in parts.items()},
            "model_version": PRESEASON_2026_MODEL_VERSION,
            "anchor": PRESEASON_2026_ANCHOR,
            "frozen": True,
        })

    output.sort(key=lambda r: r["power_rating"], reverse=True)
    for rank, row in enumerate(output, 1):
        row["rank"] = rank

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=4), encoding="utf-8")
    print(f"Frozen 2026 preseason ratings: {len(output)} teams")
    print(f"Saved to: {OUTPUT}")
    print(f"Model: {PRESEASON_2026_MODEL_VERSION}")


if __name__ == "__main__":
    main()
