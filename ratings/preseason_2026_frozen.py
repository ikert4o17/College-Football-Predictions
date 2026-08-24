"""Freeze the approved 2026 Project Gridiron preseason ratings.

Architecture:
- 2026 preseason SP+ mapped to the Project Gridiron scale
- Balanced Light overlay
  RP +1.25, transfer talent +1.00, QB -0.25, coaching +0.50
- +/-4 point total overlay cap

Writes the canonical production file expected by downstream prediction code.
"""
import json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data/processed/preseason_ratings_v4_2026_sp_anchor.json"
OUTPUT = ROOT / "data/processed/preseason_ratings_v4_2026.json"
FEATURES = ["returning_production", "transfer_talent", "qb_continuity", "coaching"]
WEIGHTS = {"returning_production": 1.25, "transfer_talent": 1.00, "qb_continuity": -0.25, "coaching": 0.50}
CAP = 4.0

def avg(xs): return sum(xs)/len(xs) if xs else 0.0
def sd(xs):
    if not xs: return 0.0
    m=avg(xs); return math.sqrt(sum((x-m)**2 for x in xs)/len(xs))
def z(x,m,s): return (x-m)/s if s else 0.0

with INPUT.open(encoding="utf-8") as f:
    rows=json.load(f)
ctx={k:(avg([float(r["preseason_features"][k]) for r in rows]), sd([float(r["preseason_features"][k]) for r in rows])) for k in FEATURES}

out=[]
for r in rows:
    parts={k:z(float(r["preseason_features"][k]), *ctx[k])*w for k,w in WEIGHTS.items()}
    raw=sum(parts.values())
    adj=max(-CAP,min(CAP,raw))
    nr=dict(r)
    nr["power_rating"]=round(float(r["baseline_sp_mapped"])+adj,4)
    nr["preseason_v4_adjustment"]=round(adj,4)
    nr["adjustment_parts"]={k:round(v,4) for k,v in parts.items()}
    nr["model_version"]="2026_preseason_balanced_light_frozen"
    nr["preseason_anchor"]="2026 preseason SP+"
    nr["overlay_name"]="balanced_light"
    nr["overlay_weights"]=WEIGHTS
    nr["overlay_cap"]=CAP
    out.append(nr)

out.sort(key=lambda r:r["power_rating"], reverse=True)
for i,r in enumerate(out,1): r["rank"]=i
OUTPUT.write_text(json.dumps(out,indent=4),encoding="utf-8")
print(f"Frozen {len(out)} 2026 preseason ratings to {OUTPUT}")
print("Balanced Light:", WEIGHTS, "cap", CAP)
for r in out[:25]: print(f"{r['rank']:>2}. {r['team']}: {r['power_rating']:+.2f} ({r['preseason_v4_adjustment']:+.2f})")
