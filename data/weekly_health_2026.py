"""Project Gridiron 2026 weekly health/completeness audit.

Runs near the end of the weekly operating system and produces a machine-readable
health report. Critical integrity failures exit non-zero so incomplete or
internally inconsistent model state is not published silently.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
SITE = ROOT / "site_data"
OUT = PROCESSED / "weekly_health_2026.json"


def load(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main():
    required = {
        "preseason": PROCESSED / "preseason_ratings_2026.json",
        "ratings": PROCESSED / "inseason_ratings_2026.json",
        "predictions": PROCESSED / "game_predictions_2026.json",
        "state": PROCESSED / "weekly_state_2026.json",
        "performance": PROCESSED / "model_performance_2026.json",
        "site_rankings": SITE / "rankings_2026.json",
        "site_predictions": SITE / "game_predictions_2026.json",
        "site_performance": SITE / "model_performance_2026.json",
    }

    critical = []
    warnings = []
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        critical.append("Missing required files: " + ", ".join(missing))

    metrics = {}
    if not missing:
        preseason = load(required["preseason"])
        ratings_doc = load(required["ratings"])
        predictions_doc = load(required["predictions"])
        state = load(required["state"])
        performance = load(required["performance"])
        manifest = load(required["site_rankings"])
        site_predictions = load(required["site_predictions"])

        ratings = ratings_doc.get("ratings", ratings_doc if isinstance(ratings_doc, list) else [])
        predictions = predictions_doc if isinstance(predictions_doc, list) else predictions_doc.get("predictions", [])
        applied = ratings_doc.get("games_applied", [])

        teams = [r.get("team") for r in ratings if r.get("team")]
        game_ids = [str(g.get("game_id")) for g in applied if g.get("game_id") is not None]
        pred_ids = [str(g.get("game_id")) for g in predictions if g.get("game_id") is not None]
        fcs_predictions = [p for p in predictions if p.get("projection_type") == "fbs_fcs"]
        fbs_predictions = [p for p in predictions if p.get("projection_type") != "fbs_fcs"]

        metrics = {
            "preseason_teams": len(preseason),
            "live_teams": len(ratings),
            "games_applied": len(applied),
            "upcoming_predictions": len(predictions),
            "upcoming_fbs_vs_fbs_predictions": len(fbs_predictions),
            "upcoming_fbs_vs_fcs_projections": len(fcs_predictions),
            "latest_completed_week": state.get("latest_completed_week"),
            "graded_games": performance.get("cumulative", {}).get("games", 0),
        }

        if len(preseason) < 130:
            critical.append(f"Frozen preseason team count is incomplete: {len(preseason)}")
        if len(ratings) < 130:
            critical.append(f"Live rating team count is incomplete: {len(ratings)}")
        if len(teams) != len(set(teams)):
            critical.append("Duplicate team names detected in live ratings")
        if len(game_ids) != len(set(game_ids)):
            critical.append("Duplicate game application detected")
        if len(pred_ids) != len(set(pred_ids)):
            critical.append("Duplicate upcoming prediction game IDs detected")
        if manifest.get("teams") != len(ratings):
            critical.append("Website ranking manifest team count does not match live ratings")
        if state.get("completed_fbs_vs_fbs_games", 0) < len(applied):
            critical.append("Weekly state completed-game count is below games applied to ratings")
        if len(site_predictions) != len(predictions):
            critical.append("Website prediction count does not match processed prediction count")

        missing_rating_fields = [r.get("team", "?") for r in ratings if r.get("power_rating") is None]
        if missing_rating_fields:
            critical.append(f"Teams missing power ratings: {len(missing_rating_fields)}")

        incomplete_preds = []
        bad_fcs_flags = []
        for p in predictions:
            if p.get("projection_type") == "fbs_fcs":
                # FBS-FCS is deliberately spread-only. Totals and implied scores
                # are unavailable because FCS teams do not use the production
                # offense/defense component model.
                needed = ("home_team", "away_team", "projected_winner", "projected_margin")
                if p.get("affects_fbs_ratings") is not False or not p.get("fcs_projection_only"):
                    bad_fcs_flags.append(p.get("game_id", "?"))
            else:
                needed = ("home_team", "away_team", "projected_winner", "projected_margin", "projected_total")
            if any(p.get(k) is None for k in needed):
                incomplete_preds.append(p.get("game_id", "?"))
        if incomplete_preds:
            critical.append(f"Incomplete prediction records: {len(incomplete_preds)}")
        if bad_fcs_flags:
            critical.append(f"FBS-FCS projections missing isolation flags: {len(bad_fcs_flags)}")

        if not predictions:
            warnings.append("No upcoming predictions are currently published")
        if performance.get("cumulative", {}).get("games", 0) == 0:
            warnings.append("No completed published predictions have been graded yet")

        for part in manifest.get("parts", []):
            if not (ROOT / part).exists():
                critical.append(f"Missing ranking part: {part}")

    status = "FAIL" if critical else ("WARN" if warnings else "PASS")
    report = {
        "season": 2026,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "metrics": metrics,
        "critical_errors": critical,
        "warnings": warnings,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 78)
    print("PROJECT GRIDIRON 2026 WEEKLY HEALTH AUDIT")
    print("=" * 78)
    print("Status:", status)
    for key, value in metrics.items():
        print(f"{key}: {value}")
    for warning in warnings:
        print("WARNING:", warning)
    for error in critical:
        print("CRITICAL:", error)

    if critical:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
