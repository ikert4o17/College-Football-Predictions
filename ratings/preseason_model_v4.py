"""Project Gridiron combined preseason model V4 validation."""
import json
import math
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "data" / "processed"
FILES = {
    "sp": ROOT / "data" / "raw" / "sp_ratings" / "2024.json",
    "g24": P / "power_ratings_2024.json",
    "g25": P / "power_ratings_2025.json",
    "rp": P / "returning_production_2025.json",
    "tt": P / "transfer_talent_2025.json",
    "tp": P / "transfer_production_v2_2025.json",
    "qb": P / "qb_continuity_2025.json",
    "coach": P / "coaching_continuity_v2_2025.json",
}
OUTPUT = P / "preseason_model_v4_validation_2025.json"
FEATURES = ["returning_production", "transfer_talent", "transfer_production", "qb_continuity", "coaching"]
GRIDS = {
    "returning_production": [0, .25, .5, .75, 1],
    "transfer_talent": [0, .25, .5, .75, 1],
    "transfer_production": [0, .25, .5, .75, 1, 1.25, 1.5],
    "qb_continuity": [0, .25, .5],
    "coaching": [0, .25, .5, .75, 1],
}
MAX_ADJ = 6.0


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
    # Current transfer_talent schema stores the validated net high-end count here.
    return get(r, "net", "high_end_count")


def extract_tp(r):
    return get(r, "net", "qb_talent_production_score") + get(r, "net", "skill_talent_production_score")


def extract_qb(r):
    # Current qb_continuity schema stores signed primary-QB pass usage here.
    return get(r, "continuity_score")


def extract_coach(r):
    return get(r, "change_after_losing_season")


def resolve():
    descriptions = {
        "sp":"2024 SP+ baseline", "g24":"2024 Project Gridiron ratings",
        "g25":"2025 Project Gridiron validation target", "rp":"2025 returning production",
        "tt":"2025 transfer talent", "tp":"2025 transfer production V2",
        "qb":"2025 QB continuity", "coach":"2025 coaching continuity V2",
    }
    print("="*78); print("PRESEASON MODEL V4 INPUT STATUS"); print("="*78); print("\nAVAILABLE\n"+"-"*78)
    missing=[]
    for k,p in FILES.items():
        if p.exists(): print(f"FOUND: {descriptions[k]}\n  {p}")
        else: missing.append((k,p))
    print("\nMISSING\n"+"-"*78)
    if missing:
        for k,p in missing: print(f"MISSING: {descriptions[k]}\n  {p}")
        raise FileNotFoundError("Full preseason model V4 validation is blocked by missing inputs.")
    print("None. Full V4 validation can run.\n")


def build():
    ls = {k: lookup(load(p)) for k,p in FILES.items()}
    teams=[]
    for name in sorted(ls["g24"]):
        if name not in ls["g25"] or name not in ls["sp"]: continue
        teams.append({
            "team": name, "sp_2024": get(ls["sp"][name], "rating"),
            "gridiron_2024": get(ls["g24"][name], "power_rating"),
            "actual_2025": get(ls["g25"][name], "power_rating"),
            "returning_production": extract_rp(ls["rp"].get(name,{})),
            "transfer_talent": extract_tt(ls["tt"].get(name,{})),
            "transfer_production": extract_tp(ls["tp"].get(name,{})),
            "qb_continuity": extract_qb(ls["qb"].get(name,{})),
            "coaching": extract_coach(ls["coach"].get(name,{})),
        })
    return teams


def contexts(teams):
    return {k:{"mean":avg([t[k] for t in teams]), "std":sd([t[k] for t in teams]),
               "min":min(t[k] for t in teams), "max":max(t[k] for t in teams)} for k in FEATURES}


def sp_context(teams):
    a=[t["sp_2024"] for t in teams]; b=[t["gridiron_2024"] for t in teams]
    return avg(a), sd(a), avg(b), sd(b)


def baseline(t, sc):
    sm,ss,gm,gs=sc
    return gm + z(t["sp_2024"],sm,ss)*gs


def adjustment(t, fc, weights):
    parts={k:z(t[k],fc[k]["mean"],fc[k]["std"])*weights[k] for k in FEATURES}
    total=max(-MAX_ADJ,min(MAX_ADJ,sum(parts.values())))
    return total,parts


def evaluate(teams, sc, fc, weights):
    pred=[]; actual=[]; adjs=[]
    for t in teams:
        a,_=adjustment(t,fc,weights); pred.append(baseline(t,sc)+a); actual.append(t["actual_2025"]); adjs.append(a)
    out=metrics(pred,actual); out.update({"weights":dict(weights),"average_absolute_adjustment":avg([abs(x) for x in adjs]),"maximum_absolute_adjustment":max(abs(x) for x in adjs)})
    return out


def improves(m,b):
    return m["correlation"]>b["correlation"] and m["mae"]<b["mae"] and m["rmse"]<b["rmse"]


def score(m,b):
    return (m["correlation"]-b["correlation"])*100 + (b["mae"]-m["mae"]) + (b["rmse"]-m["rmse"]) - .02*m["average_absolute_adjustment"]


def analyze():
    resolve(); teams=build(); fc=contexts(teams); sc=sp_context(teams)
    bp=[baseline(t,sc) for t in teams]; actual=[t["actual_2025"] for t in teams]; b=metrics(bp,actual)
    print("="*78); print("PROJECT GRIDIRON PRESEASON MODEL V4"); print("="*78)
    print(f"Teams tested: {len(teams)}\n\nSP+ BASELINE\n"+"-"*78)
    print(f"Correlation: {b['correlation']:.4f}\nMAE: {b['mae']:.2f}\nRMSE: {b['rmse']:.2f}")
    print("\nFEATURE DISTRIBUTIONS\n"+"-"*78)
    for k in FEATURES:
        c=fc[k]; print(f"{k}: mean={c['mean']:.4f}, std={c['std']:.4f}, min={c['min']:.4f}, max={c['max']:.4f}")
    results=[]
    for vals in product(*(GRIDS[k] for k in FEATURES)):
        w=dict(zip(FEATURES,vals)); m=evaluate(teams,sc,fc,w); m["improves_all"]=improves(m,b); m["score"]=score(m,b) if m["improves_all"] else None; results.append(m)
    valid=sorted([m for m in results if m["improves_all"]],key=lambda x:x["score"],reverse=True)
    print("\nGRID SEARCH\n"+"-"*78); print(f"Parameter combinations tested: {len(results)}\nModels improving all three metrics: {len(valid)}")
    print("\nTOP 20 VALID V4 MODELS\n"+"-"*78)
    for i,m in enumerate(valid[:20],1):
        w=m["weights"]; print(f"{i}. RP={w['returning_production']:.2f}, TT={w['transfer_talent']:.2f}, TP={w['transfer_production']:.2f}, QB={w['qb_continuity']:.2f}, COACH={w['coaching']:.2f}, corr={m['correlation']:.4f}, MAE={m['mae']:.2f}, RMSE={m['rmse']:.2f}, avg_adj={m['average_absolute_adjustment']:.2f}")
    best=valid[0] if valid else None; diagnostics=[]
    print("\nBEST COMBINED MODEL\n"+"-"*78)
    if best:
        w=best["weights"]
        print(f"Returning production: {w['returning_production']:.2f} pts/std\nTransfer talent: {w['transfer_talent']:.2f} pts/std\nTransfer production: {w['transfer_production']:.2f} pts/std\nQB continuity: {w['qb_continuity']:.2f} pts/std\nCoaching: {w['coaching']:.2f} pts/std")
        print(f"\nBaseline correlation: {b['correlation']:.4f}\nV4 correlation: {best['correlation']:.4f}\nCorrelation improvement: {best['correlation']-b['correlation']:+.4f}")
        print(f"\nBaseline MAE: {b['mae']:.2f}\nV4 MAE: {best['mae']:.2f}\nMAE improvement: {b['mae']-best['mae']:+.2f}")
        print(f"\nBaseline RMSE: {b['rmse']:.2f}\nV4 RMSE: {best['rmse']:.2f}\nRMSE improvement: {b['rmse']-best['rmse']:+.2f}")
        print(f"\nAverage absolute adjustment: {best['average_absolute_adjustment']:.2f}\nMaximum absolute adjustment: {best['maximum_absolute_adjustment']:.2f}")
        for t in teams:
            a,parts=adjustment(t,fc,w); base=baseline(t,sc); proj=base+a
            diagnostics.append({"team":t["team"],"baseline":base,"adjustment":a,"projection":proj,"actual":t["actual_2025"],"error":proj-t["actual_2025"],"adjustment_parts":parts})
        for title, rows in [("BIGGEST POSITIVE V4 ADJUSTMENTS",sorted(diagnostics,key=lambda x:x["adjustment"],reverse=True)[:15]),("BIGGEST NEGATIVE V4 ADJUSTMENTS",sorted(diagnostics,key=lambda x:x["adjustment"])[:15])]:
            print("\n"+title+"\n"+"-"*78)
            for r in rows:
                p=r["adjustment_parts"]; print(f"{r['team']}: {r['baseline']:.2f} -> {r['projection']:.2f} ({r['adjustment']:+.2f}), actual={r['actual']:.2f}, RP={p['returning_production']:+.2f}, TT={p['transfer_talent']:+.2f}, TP={p['transfer_production']:+.2f}, QB={p['qb_continuity']:+.2f}, coach={p['coaching']:+.2f}")
        print("\nLARGEST V4 MODEL ERRORS\n"+"-"*78)
        for r in sorted(diagnostics,key=lambda x:abs(x["error"]),reverse=True)[:15]: print(f"{r['team']}: projection={r['projection']:.2f}, actual={r['actual']:.2f}, error={r['error']:+.2f}, adjustment={r['adjustment']:+.2f}")
    else: print("No tested combined model improved correlation, MAE, and RMSE simultaneously.")
    out={"season":2025,"teams_tested":len(teams),"baseline":b,"feature_context":fc,"parameter_combinations_tested":len(results),"valid_model_count":len(valid),"best_model":best,"top_models":valid[:50],"team_diagnostics":diagnostics}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with OUTPUT.open("w",encoding="utf-8") as f: json.dump(out,f,indent=4)
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__": analyze()
