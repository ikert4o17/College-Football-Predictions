"""Project Gridiron preseason V4 multi-year aggregate audit.

Evaluates one common preseason weight vector across the 2023->2024 and
2024->2025 transitions. Each season gets its own SP+/Gridiron mapping and
feature standardization, while the weights are shared across seasons.
"""
import json
import math
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "data" / "processed"
R = ROOT / "data" / "raw"
FEATURES = ["returning_production", "transfer_talent", "transfer_production", "qb_continuity", "coaching"]
MAX_ADJ = 6.0
OUTPUT = P / "preseason_model_v4_multiyear_audit.json"

SEASONS = {
    2024: {
        "sp": R / "sp_ratings" / "2023.json",
        "g_prev": P / "power_ratings_2023.json",
        "g_target": P / "power_ratings_2024.json",
        "rp": P / "returning_production_2024.json",
        "tt": P / "transfer_talent_2024.json",
        "tp": P / "transfer_production_v2_2024.json",
        "qb": P / "qb_continuity_2024.json",
        "coach": P / "coaching_continuity_v2_2024.json",
    },
    2025: {
        "sp": R / "sp_ratings" / "2024.json",
        "g_prev": P / "power_ratings_2024.json",
        "g_target": P / "power_ratings_2025.json",
        "rp": P / "returning_production_2025.json",
        "tt": P / "transfer_talent_2025.json",
        "tp": P / "transfer_production_v2_2025.json",
        "qb": P / "qb_continuity_2025.json",
        "coach": P / "coaching_continuity_v2_2025.json",
    },
}

GRIDS = {
    "returning_production": [0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
    "transfer_talent": [0.0, 0.5, 1.0, 1.5, 2.0],
    "transfer_production": [0.0, 0.5, 1.0, 1.5, 2.0],
    "qb_continuity": [-0.5, 0.0, 0.25, 0.5],
    "coaching": [0.0, 0.5, 1.0, 1.5, 2.0],
}


def load(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def lookup(rows):
    return {r["team"]: r for r in rows if isinstance(r, dict) and r.get("team")}


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
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs)) if xs else 0.0


def z(x, m, s):
    return (x - m) / s if s else 0.0


def corr(xs, ys):
    mx, my = avg(xs), avg(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else 0.0


def metrics(pred, actual):
    return {
        "correlation": corr(pred, actual),
        "mae": avg([abs(p - a) for p, a in zip(pred, actual)]),
        "rmse": math.sqrt(avg([(p - a) ** 2 for p, a in zip(pred, actual)])),
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


def prepare(target_year, files):
    ls = {k: lookup(load(p)) for k, p in files.items()}
    teams = []
    for name in sorted(ls["g_prev"]):
        if name not in ls["g_target"] or name not in ls["sp"]:
            continue
        teams.append({
            "team": name,
            "sp": get(ls["sp"][name], "rating"),
            "gridiron_prev": get(ls["g_prev"][name], "power_rating"),
            "actual": get(ls["g_target"][name], "power_rating"),
            "returning_production": extract_rp(ls["rp"].get(name, {})),
            "transfer_talent": extract_tt(ls["tt"].get(name, {})),
            "transfer_production": extract_tp(ls["tp"].get(name, {})),
            "qb_continuity": extract_qb(ls["qb"].get(name, {})),
            "coaching": extract_coach(ls["coach"].get(name, {})),
        })
    fc = {k: {"mean": avg([t[k] for t in teams]), "std": sd([t[k] for t in teams])} for k in FEATURES}
    sp = [t["sp"] for t in teams]
    gp = [t["gridiron_prev"] for t in teams]
    sc = (avg(sp), sd(sp), avg(gp), sd(gp))
    return {"year": target_year, "teams": teams, "fc": fc, "sc": sc}


def baseline(t, sc):
    sm, ss, gm, gs = sc
    return gm + z(t["sp"], sm, ss) * gs


def evaluate_season(ctx, weights):
    pred, actual, adjs = [], [], []
    for t in ctx["teams"]:
        parts = [z(t[k], ctx["fc"][k]["mean"], ctx["fc"][k]["std"]) * weights[k] for k in FEATURES]
        adj = max(-MAX_ADJ, min(MAX_ADJ, sum(parts)))
        pred.append(baseline(t, ctx["sc"]) + adj)
        actual.append(t["actual"])
        adjs.append(adj)
    out = metrics(pred, actual)
    out["avg_abs_adj"] = avg([abs(x) for x in adjs])
    out["max_abs_adj"] = max(abs(x) for x in adjs)
    return out


def main():
    print("=" * 78)
    print("PROJECT GRIDIRON PRESEASON V4 MULTI-YEAR AUDIT")
    print("=" * 78)

    missing = []
    for year, files in SEASONS.items():
        for key, path in files.items():
            if not path.exists():
                missing.append((year, key, path))
    if missing:
        for year, key, path in missing:
            print(f"MISSING {year} {key}: {path}")
        raise FileNotFoundError("Multi-year audit blocked by missing inputs.")

    contexts = {year: prepare(year, files) for year, files in SEASONS.items()}
    baselines = {}
    for year, ctx in contexts.items():
        bp = [baseline(t, ctx["sc"]) for t in ctx["teams"]]
        actual = [t["actual"] for t in ctx["teams"]]
        baselines[year] = metrics(bp, actual)
        b = baselines[year]
        print(f"{year}: teams={len(ctx['teams'])}, baseline corr={b['correlation']:.4f}, MAE={b['mae']:.3f}, RMSE={b['rmse']:.3f}")

    total = 1
    for k in FEATURES:
        total *= len(GRIDS[k])
    print(f"\nParameter combinations: {total:,}")

    results = []
    for vals in product(*(GRIDS[k] for k in FEATURES)):
        w = dict(zip(FEATURES, vals))
        season_metrics = {year: evaluate_season(ctx, w) for year, ctx in contexts.items()}
        avg_corr = avg([m["correlation"] for m in season_metrics.values()])
        avg_mae = avg([m["mae"] for m in season_metrics.values()])
        avg_rmse = avg([m["rmse"] for m in season_metrics.values()])
        avg_adj = avg([m["avg_abs_adj"] for m in season_metrics.values()])
        improves_both_all = all(
            season_metrics[y]["correlation"] > baselines[y]["correlation"] and
            season_metrics[y]["mae"] < baselines[y]["mae"] and
            season_metrics[y]["rmse"] < baselines[y]["rmse"]
            for y in contexts
        )
        results.append({
            "weights": w,
            "seasons": season_metrics,
            "avg_correlation": avg_corr,
            "avg_mae": avg_mae,
            "avg_rmse": avg_rmse,
            "avg_abs_adj": avg_adj,
            "improves_both_all": improves_both_all,
        })

    robust = [r for r in results if r["improves_both_all"]]
    print(f"Models improving corr/MAE/RMSE in BOTH seasons: {len(robust):,}")

    base_avg = {
        "correlation": avg([b["correlation"] for b in baselines.values()]),
        "mae": avg([b["mae"] for b in baselines.values()]),
        "rmse": avg([b["rmse"] for b in baselines.values()]),
    }
    print(f"Baseline average: corr={base_avg['correlation']:.4f}, MAE={base_avg['mae']:.3f}, RMSE={base_avg['rmse']:.3f}")

    def show(title, rows):
        print("\n" + title)
        print("-" * 78)
        for i, r in enumerate(rows[:15], 1):
            w = r["weights"]
            print(
                f"{i}. RP={w['returning_production']:+.2f}, TT={w['transfer_talent']:+.2f}, "
                f"TP={w['transfer_production']:+.2f}, QB={w['qb_continuity']:+.2f}, COACH={w['coaching']:+.2f} | "
                f"avg corr={r['avg_correlation']:.4f}, MAE={r['avg_mae']:.3f}, RMSE={r['avg_rmse']:.3f}, adj={r['avg_abs_adj']:.2f}"
            )
            for y in sorted(r["seasons"]):
                m = r["seasons"][y]
                print(f"   {y}: corr={m['correlation']:.4f}, MAE={m['mae']:.3f}, RMSE={m['rmse']:.3f}")

    by_mae = sorted(robust, key=lambda r: (r["avg_mae"], r["avg_rmse"], -r["avg_correlation"], r["avg_abs_adj"]))
    by_rmse = sorted(robust, key=lambda r: (r["avg_rmse"], r["avg_mae"], -r["avg_correlation"], r["avg_abs_adj"]))
    by_corr = sorted(robust, key=lambda r: (-r["avg_correlation"], r["avg_mae"], r["avg_rmse"], r["avg_abs_adj"]))
    show("BEST ROBUST MODELS BY AVERAGE MAE", by_mae)
    show("BEST ROBUST MODELS BY AVERAGE RMSE", by_rmse)
    show("BEST ROBUST MODELS BY AVERAGE CORRELATION", by_corr)

    # Pareto frontier on the three aggregate metrics.
    frontier = []
    for r in robust:
        dominated = False
        for n in robust:
            if n is r:
                continue
            no_worse = n["avg_correlation"] >= r["avg_correlation"] and n["avg_mae"] <= r["avg_mae"] and n["avg_rmse"] <= r["avg_rmse"]
            strict = n["avg_correlation"] > r["avg_correlation"] or n["avg_mae"] < r["avg_mae"] or n["avg_rmse"] < r["avg_rmse"]
            if no_worse and strict:
                dominated = True
                break
        if not dominated:
            frontier.append(r)
    frontier.sort(key=lambda r: (r["avg_mae"] + r["avg_rmse"], -r["avg_correlation"], r["avg_abs_adj"]))
    show("MULTI-YEAR PARETO FRONTIER", frontier)

    winner = by_mae[0] if by_mae else None
    if winner:
        print("\nRECOMMENDED POINT-ERROR WINNER")
        print("-" * 78)
        w = winner["weights"]
        print(f"RP={w['returning_production']:+.2f}, TT={w['transfer_talent']:+.2f}, TP={w['transfer_production']:+.2f}, QB={w['qb_continuity']:+.2f}, COACH={w['coaching']:+.2f}")
        print(f"Average correlation: {winner['avg_correlation']:.4f} ({winner['avg_correlation']-base_avg['correlation']:+.4f})")
        print(f"Average MAE: {winner['avg_mae']:.3f} ({base_avg['mae']-winner['avg_mae']:+.3f} improvement)")
        print(f"Average RMSE: {winner['avg_rmse']:.3f} ({base_avg['rmse']-winner['avg_rmse']:+.3f} improvement)")
        print(f"Average absolute adjustment: {winner['avg_abs_adj']:.2f}")

    out = {
        "seasons": sorted(contexts),
        "baseline_average": base_avg,
        "parameter_combinations": total,
        "robust_model_count": len(robust),
        "best_by_mae": by_mae[:50],
        "best_by_rmse": by_rmse[:50],
        "best_by_correlation": by_corr[:50],
        "pareto_frontier": frontier,
        "recommended": winner,
    }
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
