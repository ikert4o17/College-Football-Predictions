"""Compare lighter Project Gridiron overlays on top of 2026 preseason SP+.

This is a structural sensitivity test, not a historical backtest. It keeps the
2026 preseason SP+ mapped anchor fixed and varies only the Gridiron overlay.
"""
import json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data/processed/preseason_ratings_v4_2026_sp_anchor.json"
OUTPUT = ROOT / "data/processed/preseason_2026_light_overlay_comparison.json"
SUMMARY = ROOT / "data/processed/preseason_2026_light_overlay_summary.json"
FEATURES = ["returning_production", "transfer_talent", "qb_continuity", "coaching"]

CANDIDATES = {
    "sp_only": {"weights": {k: 0.0 for k in FEATURES}, "cap": 0.0},
    "full_v4": {"weights": {"returning_production": 2.0, "transfer_talent": 0.5, "qb_continuity": -0.5, "coaching": 2.0}, "cap": 6.0},
    "balanced_light": {"weights": {"returning_production": 1.25, "transfer_talent": 1.00, "qb_continuity": -0.25, "coaching": 0.50}, "cap": 4.0},
    "talent_forward": {"weights": {"returning_production": 1.25, "transfer_talent": 1.25, "qb_continuity": -0.25, "coaching": 0.50}, "cap": 4.0},
    "conservative_talent": {"weights": {"returning_production": 1.00, "transfer_talent": 1.00, "qb_continuity": -0.25, "coaching": 0.25}, "cap": 3.0},
    "talent_heavy": {"weights": {"returning_production": 1.00, "transfer_talent": 1.50, "qb_continuity": -0.25, "coaching": 0.25}, "cap": 4.0},
}

def avg(xs): return sum(xs)/len(xs) if xs else 0.0
def sd(xs):
    if not xs: return 0.0
    m=avg(xs); return math.sqrt(sum((x-m)**2 for x in xs)/len(xs))
def z(x,m,s): return (x-m)/s if s else 0.0

with INPUT.open(encoding="utf-8") as f:
    rows=json.load(f)
ctx={k:(avg([float(r["preseason_features"][k]) for r in rows]), sd([float(r["preseason_features"][k]) for r in rows])) for k in FEATURES}

results={}
summary={"teams":len(rows),"candidates":{}}
for name,cfg in CANDIDATES.items():
    out=[]
    for r in rows:
        parts={}
        for k,w in cfg["weights"].items():
            x=float(r["preseason_features"][k]); m,s=ctx[k]
            parts[k]=z(x,m,s)*w
        raw=sum(parts.values())
        cap=cfg["cap"]
        adj=0.0 if cap==0 else max(-cap,min(cap,raw))
        out.append({"team":r["team"],"anchor":r["baseline_sp_mapped"],"rating":round(r["baseline_sp_mapped"]+adj,4),"adjustment":round(adj,4),"parts":{k:round(v,4) for k,v in parts.items()}})
    out.sort(key=lambda x:x["rating"], reverse=True)
    for i,r in enumerate(out,1): r["rank"]=i
    mean_abs=round(avg([abs(r["adjustment"]) for r in out]),4)
    cap_hits=sum(1 for r in out if cap and abs(r["adjustment"])>=cap-1e-9)
    largest=sorted(out,key=lambda r:abs(r["adjustment"]),reverse=True)[:20]
    results[name]={
        "weights":cfg["weights"],"cap":cap,
        "mean_abs_adjustment":mean_abs,
        "teams_at_cap":cap_hits,
        "top25":[{"rank":r["rank"],"team":r["team"],"rating":r["rating"],"adjustment":r["adjustment"]} for r in out[:25]],
        "largest_effects":largest,
    }
    summary["candidates"][name]={
        "weights":cfg["weights"],
        "cap":cap,
        "mean_abs_adjustment":mean_abs,
        "teams_at_cap":cap_hits,
        "top10":[{"rank":r["rank"],"team":r["team"],"rating":r["rating"],"adjustment":r["adjustment"]} for r in out[:10]],
        "largest_positive":[{"team":r["team"],"adjustment":r["adjustment"],"rank":r["rank"]} for r in sorted(out,key=lambda r:r["adjustment"],reverse=True)[:8]],
        "largest_negative":[{"team":r["team"],"adjustment":r["adjustment"],"rank":r["rank"]} for r in sorted(out,key=lambda r:r["adjustment"])[:8]],
    }

OUTPUT.write_text(json.dumps({"teams":len(rows),"purpose":"2026 SP+ anchor overlay sensitivity test","candidates":results},indent=2),encoding="utf-8")
SUMMARY.write_text(json.dumps(summary,indent=2),encoding="utf-8")
print("Saved", OUTPUT)
print("Saved", SUMMARY)
for name,r in results.items():
    print(f"{name}: mean_abs={r['mean_abs_adjustment']:.2f}, cap_hits={r['teams_at_cap']}")
