"""Backtest Project Gridiron in-season rating update mechanics on archived seasons.

This isolates the live update rule: predict each completed FBS-vs-FBS game from
current ratings, then update both teams from the margin residual. It reports the
best learning schedule and translates it into expected per-game/week behavior.

Historical seasons require a PRIOR-season Project Gridiron anchor. GitHub
currently contains the 2024 anchor needed to test 2025. If an older anchor is
added later (for example power_ratings_2023.json), that season is included
automatically without changing this script.

Important: these historical anchors are weaker/staler than the frozen 2026
preseason SP+ + Balanced Light anchor, so the selected learning rate should be
viewed as an upper bound for 2026 rather than a reason to learn more aggressively.
"""
import itertools, json, math
from pathlib import Path
from predictions.provisional_2026_predictions import load_margin_calibration

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"data/processed/inseason_ratings_backtest_2024_2025.json"
SEASON_CANDIDATES={
  2024:{"anchor":ROOT/"data/processed/power_ratings_2023.json","games":ROOT/"data/processed/historical_games_2024.json"},
  2025:{"anchor":ROOT/"data/processed/power_ratings_2024.json","games":ROOT/"data/processed/historical_games_2025.json"},
}
CURRENT_V1={"base_learning_rate":0.16,"learning_rate_step":0.03,"max_learning_rate":0.34,"max_margin_residual":28.0,"max_team_delta":4.0}
GRID={
 "base_learning_rate":[0.06,0.08,0.10,0.12,0.16],
 "learning_rate_step":[0.00,0.01,0.02,0.03],
 "max_learning_rate":[0.16,0.20,0.24,0.28,0.34],
 "max_margin_residual":[21.0,28.0,35.0],
 "max_team_delta":[2.0,3.0,4.0],
}

def load(p):
 with p.open(encoding="utf-8") as f:return json.load(f)
def clamp(x,a,b):return max(a,min(b,x))
def rmse(es):return math.sqrt(sum(e*e for e in es)/len(es)) if es else None
def anchor_lookup(rows):return {r["team"]:float(r["power_rating"]) for r in rows if r.get("team") and r.get("power_rating") is not None}
def eligible(rows,season):
 out=[]
 for g in rows:
  if not isinstance(g,dict) or g.get("season")!=season or g.get("season_type")!="regular" or not g.get("completed") or g.get("game_classification")!="fbs_vs_fbs":continue
  h,a=g.get("home") or {},g.get("away") or {}
  if h.get("points") is None or a.get("points") is None:continue
  out.append(g)
 out.sort(key=lambda g:(g.get("start_date") or "",g.get("game_id") or 0));return out

def available_seasons():
 active={};skipped={}
 for season,paths in SEASON_CANDIDATES.items():
  missing=[str(path.relative_to(ROOT)) for path in paths.values() if not path.exists()]
  if missing: skipped[str(season)]={"reason":"missing required historical inputs","missing":missing}
  else: active[season]=paths
 if not active:
  raise FileNotFoundError("No historical season has both a prior-season anchor and completed-game file in GitHub")
 return active,skipped

def learning_rate(params, prior_games):
 return min(params["max_learning_rate"],params["base_learning_rate"]+params["learning_rate_step"]*prior_games)

def evaluate_season(season,paths,params,coeff,hfa):
 anchor=anchor_lookup(load(paths["anchor"]));ratings=dict(anchor);gp={t:0 for t in ratings}
 updated=[];static=[];uw=sw=tested=0;buckets={i:{"updated":[],"static":[],"deltas":[]} for i in range(0,13)}
 for g in eligible(load(paths["games"]),season):
  home,away=g["home"]["team"],g["away"]["team"]
  if home not in ratings or away not in ratings:continue
  actual=float(g["home"]["points"])-float(g["away"]["points"]);hf=0.0 if g.get("neutral_site") else hfa
  up=coeff*(ratings[home]-ratings[away])+hf;st=coeff*(anchor[home]-anchor[away])+hf
  ue,se=up-actual,st-actual;updated.append(ue);static.append(se);tested+=1
  if actual!=0: uw+=int((up>0)==(actual>0));sw+=int((st>0)==(actual>0))
  prior=(gp[home]+gp[away])/2.0;bucket=min(12,int(math.floor(prior)))
  residual=clamp(actual-up,-params["max_margin_residual"],params["max_margin_residual"])
  lr=learning_rate(params,prior);delta=clamp(0.5*lr*(residual/coeff),-params["max_team_delta"],params["max_team_delta"])
  buckets[bucket]["updated"].append(ue);buckets[bucket]["static"].append(se);buckets[bucket]["deltas"].append(abs(delta))
  ratings[home]+=delta;ratings[away]-=delta;gp[home]+=1;gp[away]+=1
 if tested==0: raise ValueError(f"No eligible games could be tested for {season}")
 mae_u=sum(abs(e) for e in updated)/tested;mae_s=sum(abs(e) for e in static)/tested
 weekly={}
 for k,b in buckets.items():
  if not b["updated"]:continue
  weekly[str(k+1)]={"games":len(b["updated"]),"updated_mae":round(sum(abs(e) for e in b["updated"])/len(b["updated"]),3),"static_mae":round(sum(abs(e) for e in b["static"])/len(b["static"]),3),"avg_abs_team_delta":round(sum(b["deltas"])/len(b["deltas"]),3)}
 return {"games_tested":tested,"updated_mae":round(mae_u,4),"static_mae":round(mae_s,4),"mae_improvement":round(mae_s-mae_u,4),"updated_rmse":round(rmse(updated),4),"static_rmse":round(rmse(static),4),"rmse_improvement":round(rmse(static)-rmse(updated),4),"updated_winner_accuracy":round(uw/tested,4),"static_winner_accuracy":round(sw/tested,4),"by_team_game_number":weekly}

def evaluate(params,coeff,hfa,seasons):
 results={str(y):evaluate_season(y,paths,params,coeff,hfa) for y,paths in seasons.items()}
 n=len(results);mi=sum(v["mae_improvement"] for v in results.values())/n;ri=sum(v["rmse_improvement"] for v in results.values())/n
 return {"params":dict(params),"seasons":results,"mean_mae_improvement":round(mi,4),"mean_rmse_improvement":round(ri,4),"improves_mae_and_rmse_all_available_seasons":all(v["mae_improvement"]>0 and v["rmse_improvement"]>0 for v in results.values())}

def schedule(params):
 return [{"team_game_number":n+1,"learning_rate":round(learning_rate(params,n),3),"max_team_delta":params["max_team_delta"]} for n in range(12)]

def main():
 seasons,skipped=available_seasons()
 cal=load_margin_calibration();coeff=float(cal["rating_gap_coefficient"]);hfa=float(cal["home_field_advantage"])
 current=evaluate(CURRENT_V1,coeff,hfa,seasons);keys=list(GRID);cands=[]
 for vals in itertools.product(*(GRID[k] for k in keys)):cands.append(evaluate(dict(zip(keys,vals)),coeff,hfa,seasons))
 valid=[c for c in cands if c["improves_mae_and_rmse_all_available_seasons"]]
 ranked=sorted(valid or cands,key=lambda c:(-c["mean_mae_improvement"],-c["mean_rmse_improvement"],c["params"]["max_team_delta"],c["params"]["max_learning_rate"],c["params"]["base_learning_rate"]))
 best=ranked[0]
 result={
  "method":"sequential margin-residual update vs static prior-season anchor",
  "tested_seasons":sorted(seasons),
  "skipped_seasons":skipped,
  "caveat":"Historical anchor is weaker/staler than frozen 2026 preseason SP+ + Balanced Light; recommended learning is an upper bound for 2026. Current GitHub history supports 2025; 2024 will be added automatically if power_ratings_2023.json is restored.",
  "frozen_2026_preseason":"2026 preseason SP+ + Balanced Light (RP 1.25, TT 1.00, QB -0.25, coaching 0.50, cap 4)",
  "calibration":{"rating_gap_coefficient":coeff,"home_field_advantage":hfa},
  "parameter_combinations":len(cands),
  "valid_candidates_improving_mae_and_rmse_all_available_seasons":len(valid),
  "current_v1":current,
  "recommended":best,
  "recommended_learning_schedule":schedule(best["params"]),
  "top_20":ranked[:20]
 }
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=4),encoding="utf-8")
 print("="*78);print("PROJECT GRIDIRON WEEK-BY-WEEK IN-SEASON UPDATE BACKTEST");print("="*78)
 print("Tested seasons:",sorted(seasons));print("Skipped seasons:",skipped)
 print("Candidates:",len(cands)," valid all available seasons:",len(valid));print("Recommended:",best["params"]);print("Learning schedule:")
 for r in result["recommended_learning_schedule"]:print(f"game {r['team_game_number']:>2}: lr={r['learning_rate']:.3f}, max delta={r['max_team_delta']:.1f}")
 for s,m in best["seasons"].items():print(f"{s}: MAE improve {m['mae_improvement']:+.3f}, RMSE improve {m['rmse_improvement']:+.3f}, winner acc {m['updated_winner_accuracy']:.3f}")
 print("Saved",OUT)
if __name__=="__main__":main()
