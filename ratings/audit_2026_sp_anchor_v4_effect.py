"""Audit the incremental effect of full V4 adjustments on the 2026 preseason SP+ anchor."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "processed" / "preseason_ratings_v4_2026_sp_anchor.json"
OUTPUT = ROOT / "data" / "processed" / "preseason_2026_sp_anchor_v4_effect.json"


def main():
    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    audit = []
    for row in rows:
        base = float(row["baseline_sp_mapped"])
        final = float(row["power_rating"])
        audit.append({
            "team": row["team"],
            "sp_anchor_only": round(base, 4),
            "sp_plus_full_v4": round(final, 4),
            "v4_adjustment": round(final - base, 4),
            "final_rank": row.get("rank"),
            "adjustment_parts": row.get("adjustment_parts", {}),
            "preseason_features": row.get("preseason_features", {}),
        })

    base_ranked = sorted(audit, key=lambda r: r["sp_anchor_only"], reverse=True)
    base_ranks = {r["team"]: i for i, r in enumerate(base_ranked, 1)}
    for row in audit:
        row["sp_anchor_rank"] = base_ranks[row["team"]]
        row["rank_change_from_v4"] = row["sp_anchor_rank"] - int(row["final_rank"])

    by_abs = sorted(audit, key=lambda r: abs(r["v4_adjustment"]), reverse=True)
    summary = {
        "teams": len(audit),
        "comparison": "2026 preseason SP+ mapped anchor alone vs same anchor plus frozen full V4 adjustments",
        "mean_abs_v4_adjustment": round(sum(abs(r["v4_adjustment"]) for r in audit) / len(audit), 4),
        "teams_at_6_point_cap": sum(abs(r["v4_adjustment"]) >= 5.999 for r in audit),
        "largest_effects": by_abs,
        "sp_anchor_top25": [{"rank": i, "team": r["team"], "rating": r["sp_anchor_only"]} for i, r in enumerate(base_ranked[:25], 1)],
        "sp_plus_v4_top25": [{"rank": r["final_rank"], "team": r["team"], "rating": r["sp_plus_full_v4"], "v4_adjustment": r["v4_adjustment"]} for r in sorted(audit, key=lambda r: r["final_rank"])[:25]],
    }
    OUTPUT.write_text(json.dumps(summary, indent=4), encoding="utf-8")

    print("=" * 78)
    print("2026 PRESEASON SP+ ANCHOR: FULL V4 INCREMENTAL EFFECT")
    print("=" * 78)
    print(f"Teams: {len(audit)}")
    print(f"Mean absolute V4 adjustment: {summary['mean_abs_v4_adjustment']:.2f}")
    print(f"Teams at +/-6 cap: {summary['teams_at_6_point_cap']}")
    print("\nLARGEST V4 EFFECTS")
    for r in by_abs[:25]:
        print(f"{r['team']}: {r['sp_anchor_only']:+.2f} -> {r['sp_plus_full_v4']:+.2f} ({r['v4_adjustment']:+.2f}), rank {r['sp_anchor_rank']} -> {r['final_rank']}")
    print(f"\nSaved: {OUTPUT}")


if __name__ == "__main__":
    main()
