"""Backtest Project Gridiron in-season rating update mechanics on 2024-2025.

The test deliberately isolates the update rule: each season starts from the prior
season's Project Gridiron power ratings, predicts every completed FBS-vs-FBS game
sequentially, then updates both teams from the margin residual. Each candidate is
compared with a static-anchor baseline that never updates.

Usage:
    python -m ratings.backtest_inseason_ratings
"""

import itertools
import json
import math
from pathlib import Path

from predictions.provisional_2026_predictions import load_margin_calibration

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "processed" / "inseason_ratings_backtest_2024_2025.json"

SEASONS = {
    2024: {
        "anchor": ROOT / "data" / "processed" / "power_ratings_2023.json",
        "games": ROOT / "data" / "processed" / "historical_games_2024.json",
    },
    2025: {
        "anchor": ROOT / "data" / "processed" / "power_ratings_2024.json",
        "games": ROOT / "data" / "processed" / "historical_games_2025.json",
    },
}

CURRENT_V1 = {
    "base_learning_rate": 0.16,
    "learning_rate_step": 0.03,
    "max_learning_rate": 0.34,
    "max_margin_residual": 28.0,
    "max_team_delta": 4.0,
}

GRID = {
    "base_learning_rate": [0.08, 0.12, 0.16, 0.20],
    "learning_rate_step": [0.00, 0.02, 0.03, 0.04],
    "max_learning_rate": [0.20, 0.28, 0.34, 0.40],
    "max_margin_residual": [21.0, 28.0, 35.0],
    "max_team_delta": [2.0, 3.0, 4.0],
}


def load(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def clamp(value, low, high):
    return max(low, min(high, value))


def rmse(errors):
    return math.sqrt(sum(e * e for e in errors) / len(errors)) if errors else None


def anchor_lookup(rows):
    out = {}
    for row in rows:
        team = row.get("team")
        rating = row.get("power_rating")
        if team and rating is not None:
            out[team] = float(rating)
    return out


def eligible_games(rows, season):
    games = []
    for g in rows:
        if not isinstance(g, dict) or g.get("season") != season:
            continue
        if g.get("season_type") != "regular" or not g.get("completed"):
            continue
        if g.get("game_classification") != "fbs_vs_fbs":
            continue
        home = g.get("home") or {}
        away = g.get("away") or {}
        if home.get("points") is None or away.get("points") is None:
            continue
        games.append(g)
    games.sort(key=lambda g: (g.get("start_date") or "", g.get("game_id") or 0))
    return games


def evaluate_season(season, params, coeff, hfa):
    anchor = anchor_lookup(load(SEASONS[season]["anchor"]))
    games = eligible_games(load(SEASONS[season]["games"]), season)
    ratings = dict(anchor)
    games_played = {team: 0 for team in ratings}

    updated_errors = []
    static_errors = []
    updated_winners = 0
    static_winners = 0
    tested = 0

    for g in games:
        home = g["home"]["team"]
        away = g["away"]["team"]
        if home not in ratings or away not in ratings:
            continue

        neutral = bool(g.get("neutral_site"))
        actual = float(g["home"]["points"]) - float(g["away"]["points"])
        hf = 0.0 if neutral else hfa

        updated_pred = coeff * (ratings[home] - ratings[away]) + hf
        static_pred = coeff * (anchor[home] - anchor[away]) + hf

        updated_errors.append(updated_pred - actual)
        static_errors.append(static_pred - actual)
        updated_winners += int((updated_pred > 0) == (actual > 0)) if actual != 0 else 0
        static_winners += int((static_pred > 0) == (actual > 0)) if actual != 0 else 0
        tested += 1

        residual = clamp(
            actual - updated_pred,
            -params["max_margin_residual"],
            params["max_margin_residual"],
        )
        prior_games = (games_played[home] + games_played[away]) / 2.0
        learning = min(
            params["max_learning_rate"],
            params["base_learning_rate"] + params["learning_rate_step"] * prior_games,
        )
        delta = 0.5 * learning * (residual / coeff)
        delta = clamp(delta, -params["max_team_delta"], params["max_team_delta"])
        ratings[home] += delta
        ratings[away] -= delta
        games_played[home] += 1
        games_played[away] += 1

    mae_updated = sum(abs(e) for e in updated_errors) / tested
    mae_static = sum(abs(e) for e in static_errors) / tested
    return {
        "games_tested": tested,
        "updated_mae": round(mae_updated, 4),
        "static_mae": round(mae_static, 4),
        "mae_improvement": round(mae_static - mae_updated, 4),
        "updated_rmse": round(rmse(updated_errors), 4),
        "static_rmse": round(rmse(static_errors), 4),
        "rmse_improvement": round(rmse(static_errors) - rmse(updated_errors), 4),
        "updated_winner_accuracy": round(updated_winners / tested, 4),
        "static_winner_accuracy": round(static_winners / tested, 4),
    }


def evaluate(params, coeff, hfa):
    seasons = {str(year): evaluate_season(year, params, coeff, hfa) for year in SEASONS}
    mean_mae_improvement = sum(v["mae_improvement"] for v in seasons.values()) / len(seasons)
    mean_rmse_improvement = sum(v["rmse_improvement"] for v in seasons.values()) / len(seasons)
    improves_both = all(v["mae_improvement"] > 0 and v["rmse_improvement"] > 0 for v in seasons.values())
    return {
        "params": dict(params),
        "seasons": seasons,
        "mean_mae_improvement": round(mean_mae_improvement, 4),
        "mean_rmse_improvement": round(mean_rmse_improvement, 4),
        "improves_mae_and_rmse_both_seasons": improves_both,
    }


def main():
    for season, paths in SEASONS.items():
        for name, path in paths.items():
            if not path.exists():
                raise FileNotFoundError(f"Missing {season} {name}: {path}")

    cal = load_margin_calibration()
    coeff = float(cal["rating_gap_coefficient"])
    hfa = float(cal["home_field_advantage"])

    current = evaluate(CURRENT_V1, coeff, hfa)
    candidates = []
    keys = list(GRID)
    for values in itertools.product(*(GRID[k] for k in keys)):
        params = dict(zip(keys, values))
        candidates.append(evaluate(params, coeff, hfa))

    valid = [c for c in candidates if c["improves_mae_and_rmse_both_seasons"]]
    ranked = sorted(
        valid or candidates,
        key=lambda c: (
            -c["mean_mae_improvement"],
            -c["mean_rmse_improvement"],
            c["params"]["max_team_delta"],
            c["params"]["max_learning_rate"],
        ),
    )
    best = ranked[0]

    result = {
        "method": "sequential margin-residual update vs static prior-season anchor",
        "calibration": {"rating_gap_coefficient": coeff, "home_field_advantage": hfa},
        "parameter_combinations": len(candidates),
        "valid_candidates_improving_mae_and_rmse_both_seasons": len(valid),
        "current_v1": current,
        "recommended": best,
        "top_20": ranked[:20],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)

    print("=" * 78)
    print("PROJECT GRIDIRON IN-SEASON UPDATE BACKTEST: 2024-2025")
    print("=" * 78)
    print(f"Parameter combinations: {len(candidates)}")
    print(f"Valid on both seasons: {len(valid)}")
    print("\nCURRENT V1")
    print("-" * 78)
    print(CURRENT_V1)
    for season, metrics in current["seasons"].items():
        print(f"{season}: MAE improve {metrics['mae_improvement']:+.3f}, RMSE improve {metrics['rmse_improvement']:+.3f}, winner acc {metrics['updated_winner_accuracy']:.3f}")
    print("\nRECOMMENDED")
    print("-" * 78)
    print(best["params"])
    for season, metrics in best["seasons"].items():
        print(f"{season}: MAE improve {metrics['mae_improvement']:+.3f}, RMSE improve {metrics['rmse_improvement']:+.3f}, winner acc {metrics['updated_winner_accuracy']:.3f}")
    print(f"\nSaved to {OUT}")


if __name__ == "__main__":
    main()
