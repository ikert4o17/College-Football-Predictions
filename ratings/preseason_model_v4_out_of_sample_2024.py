"""Project Gridiron 2024 out-of-sample preseason validation.

This evaluates weight sets chosen from the 2025 development work against the
2023 -> 2024 transition WITHOUT optimizing weights on 2024 first.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "data" / "processed"
FILES = {
    "sp": ROOT / "data" / "raw" / "sp_ratings" / "2023.json",
    "g_prev": P / "power_ratings_2023.json",
    "g_target": P / "power_ratings_2024.json",
    "rp": P / "returning_production_2024.json",
    "tt": P / "transfer_talent_2024.json",
    "tp": P / "transfer_production_v2_2024.json",
    "qb": P / "qb_continuity_2024.json",
    "coach": P / "coaching_continuity_v2_2024.json",
}
OUTPUT = P / "preseason_model_v4_out_of_sample_2024.json"
FEATURES = ["returning_production", "transfer_talent", "transfer_production", "qb_continuity", "coaching"]
MAX_ADJ = 6.0

# These are intentionally fixed before looking at 2024 performance.
# They represent the main candidates produced by 2025 development/stress tests.
CANDIDATES = {
    "2025_v4_winner": {
        "returning_production": 1.00,
        "transfer_talent": 1.00,
        "transfer_production": 1.50,
        "qb_continuity": 0.00,
        "coaching": 1.00,
    },
    "2025_conservative_portal": {
        "returning_production": 1.00,
        "transfer_talent": 0.50,
        "transfer_production": 0.50,
        "qb_continuity": 0.00,
        "coaching": 2.00,
    },
    "2025_lowest_mae": {
        "returning_production": 1.25,
        "transfer_talent": 0.00,
        "transfer_production": 1.00,
        "qb_continuity": -0.50,
        "coaching": 2.00,
    },
    "balanced_portal_1x": {
        "returning_production": 1.00,
        "transfer_talent": 1.00,
        "transfer_production": 1.00,
        "qb_continuity": 0.00,
        "coaching": 1.00,
    },
}


def load(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def lookup(records):
    return {r["team"]: r for r in records if isinstance(r, dict) and r.get("team")}


def sf(v):
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def get(r, *keys, default=0.0):
    v = r
    for k in keys:
        if not isinstance(v, dict) or k not in v or v[k] is None:
            return default
        v = v[k]
    return sf(v)


def avg(xs):
    return sum(xs) / len(xs) if xs else 0.0


def sd(xs):
    m = avg(xs)
    return math.sqrt(sum((x-m)**2 for x in xs) / len(xs)) if xs else 0.0


def z(x, m, s):
    return (x-m)/s if s else 0.0


def corr(xs, ys):
    mx, my = avg(xs), avg(ys)
    num = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x-mx)**2 for x in xs) * sum((y-my)**2 for y in ys))
    return num/den if den else 0.0


def metrics(pred, actual):
    return {
        "correlation": corr(pred, actual),
        "mae": avg([abs(p-a) for p, a in zip(pred, actual)]),
        "rmse": math.sqrt(avg([(p-a)**2 for p, a in zip(pred, actual)])),
    }


def extract_rp(r):
    return get(r, "overall", "percent", default=get(r, "returning_percentage"))


def extract_tt(r):
    return get(r, "net", "high_end_count")


def extract_tp(r):
    return get(r, "net", "qb_talent_production_score") + get(r, "net", "skill_talent_production_score")


def extract_qb(r):
    return get(r, "continuity_score")


def extract_coach(r):
    return get(r, "change_after_losing_season")


def resolve():
    print("="*78)
    print("2024 OUT-OF-SAMPLE PRESEASON INPUT STATUS")
    print("="*78)
    missing = []
    for key, path in FILES.items():
        if path.exists():
            print(f"FOUND: {key:8s} {path}")
        else:
            print(f"MISSING: {key:8s} {path}")
            missing.append(path)
    if missing:
        raise FileNotFoundError("2024 out-of-sample validation blocked by missing inputs.")


def build():
    ls = {k: lookup(load(p)) for k, p in FILES.items()}
    teams = []
    for name in sorted(ls["g_prev"]):
        if name not in ls["g_target"] or name not in ls["sp"]:
            continue
        teams.append({
            "team": name,
            "sp_prev": get(ls["sp"][name], "rating"),
            "gridiron_prev": get(ls["g_prev"][name], "power_rating"),
            "actual_target": get(ls["g_target"][name], "power_rating"),
            "returning_production": extract_rp(ls["rp"].get(name, {})),
            "transfer_talent": extract_tt(ls["tt"].get(name, {})),
            "transfer_production": extract_tp(ls["tp"].get(name, {})),
            "qb_continuity": extract_qb(ls["qb"].get(name, {})),
            "coaching": extract_coach(ls["coach"].get(name, {})),
        })
    return teams


def contexts(teams):
    return {
        k: {
            "mean": avg([t[k] for t in teams]),
            "std": sd([t[k] for t in teams]),
            "min": min(t[k] for t in teams),
            "max": max(t[k] for t in teams),
        }
        for k in FEATURES
    }


def sp_context(teams):
    s = [t["sp_prev"] for t in teams]
    g = [t["gridiron_prev"] for t in teams]
    return avg(s), sd(s), avg(g), sd(g)


def baseline(t, sc):
    sm, ss, gm, gs = sc
    return gm + z(t["sp_prev"], sm, ss) * gs


def adjustment(t, fc, weights):
    parts = {
        k: z(t[k], fc[k]["mean"], fc[k]["std"]) * weights[k]
        for k in FEATURES
    }
    total = max(-MAX_ADJ, min(MAX_ADJ, sum(parts.values())))
    return total, parts


def evaluate(teams, sc, fc, weights):
    pred, actual, adjs = [], [], []
    for t in teams:
        a, _ = adjustment(t, fc, weights)
        pred.append(baseline(t, sc) + a)
        actual.append(t["actual_target"])
        adjs.append(a)
    out = metrics(pred, actual)
    out.update({
        "weights": dict(weights),
        "average_absolute_adjustment": avg([abs(x) for x in adjs]),
        "maximum_absolute_adjustment": max(abs(x) for x in adjs),
    })
    return out


def analyze():
    resolve()
    teams = build()
    fc = contexts(teams)
    sc = sp_context(teams)
    actual = [t["actual_target"] for t in teams]
    base_pred = [baseline(t, sc) for t in teams]
    b = metrics(base_pred, actual)

    print("\n" + "="*78)
    print("PROJECT GRIDIRON 2024 OUT-OF-SAMPLE PRESEASON VALIDATION")
    print("="*78)
    print(f"Teams tested: {len(teams)}")
    print("\nBASELINE (2023 SP+ mapped to 2023 Gridiron scale)")
    print("-"*78)
    print(f"Correlation: {b['correlation']:.4f}")
    print(f"MAE: {b['mae']:.3f}")
    print(f"RMSE: {b['rmse']:.3f}")

    print("\nFEATURE DISTRIBUTIONS")
    print("-"*78)
    for k in FEATURES:
        c = fc[k]
        print(f"{k}: mean={c['mean']:.4f}, std={c['std']:.4f}, min={c['min']:.4f}, max={c['max']:.4f}")

    results = {}
    print("\nFIXED 2025-DERIVED CANDIDATES ON UNSEEN 2024")
    print("-"*78)
    for name, weights in CANDIDATES.items():
        m = evaluate(teams, sc, fc, weights)
        m["correlation_change"] = m["correlation"] - b["correlation"]
        m["mae_improvement"] = b["mae"] - m["mae"]
        m["rmse_improvement"] = b["rmse"] - m["rmse"]
        m["improves_all"] = (
            m["correlation"] > b["correlation"]
            and m["mae"] < b["mae"]
            and m["rmse"] < b["rmse"]
        )
        results[name] = m
        w = weights
        print(
            f"{name}: RP={w['returning_production']:+.2f}, TT={w['transfer_talent']:+.2f}, "
            f"TP={w['transfer_production']:+.2f}, QB={w['qb_continuity']:+.2f}, COACH={w['coaching']:+.2f}"
        )
        print(
            f"  corr={m['correlation']:.4f} ({m['correlation_change']:+.4f}), "
            f"MAE={m['mae']:.3f} (improve {m['mae_improvement']:+.3f}), "
            f"RMSE={m['rmse']:.3f} (improve {m['rmse_improvement']:+.3f}), "
            f"avg_adj={m['average_absolute_adjustment']:.2f}, max_adj={m['maximum_absolute_adjustment']:.2f}, "
            f"improves_all={m['improves_all']}"
        )

    ranked = sorted(
        results.items(),
        key=lambda kv: (kv[1]["mae"], kv[1]["rmse"], -kv[1]["correlation"]),
    )
    print("\nRANKING BY OUT-OF-SAMPLE MAE")
    print("-"*78)
    for i, (name, m) in enumerate(ranked, 1):
        print(f"{i}. {name}: MAE={m['mae']:.3f}, RMSE={m['rmse']:.3f}, corr={m['correlation']:.4f}")

    out = {
        "target_season": 2024,
        "development_season": 2025,
        "teams_tested": len(teams),
        "baseline": b,
        "feature_context": fc,
        "candidate_results": results,
        "ranking_by_mae": [name for name, _ in ranked],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=4)
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    analyze()
