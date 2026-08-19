"""Project Gridiron preseason portal-weight stress test.

Tests whether transfer talent / production want materially more weight than
allowed by the initial V4 grid. Reuses V4's validated feature extraction,
standardization, baseline, adjustment cap, and evaluation functions.
"""
from itertools import product

from ratings import preseason_model_v4 as v4

# Deliberately wider than V4. Negative values are included as a directionality
# sanity check; portal features extend to +5 because V4's transfer-production
# winner landed on its original +1.50 boundary.
GRIDS = {
    "returning_production": [-1.0, -0.5, 0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
    "transfer_talent": [-3.0, -2.0, -1.0, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0],
    "transfer_production": [-3.0, -2.0, -1.0, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0],
    "qb_continuity": [-2.0, -1.0, -0.5, 0.0, 0.25, 0.5, 1.0, 2.0],
    "coaching": [-1.0, -0.5, 0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
}


def fmt(m):
    w = m["weights"]
    return (
        f"RP={w['returning_production']:+.2f}, TT={w['transfer_talent']:+.2f}, "
        f"TP={w['transfer_production']:+.2f}, QB={w['qb_continuity']:+.2f}, "
        f"COACH={w['coaching']:+.2f}, corr={m['correlation']:.4f}, "
        f"MAE={m['mae']:.3f}, RMSE={m['rmse']:.3f}, "
        f"avg_adj={m['average_absolute_adjustment']:.2f}, "
        f"max_adj={m['maximum_absolute_adjustment']:.2f}"
    )


def analyze():
    v4.resolve()
    teams = v4.build()
    fc = v4.contexts(teams)
    sc = v4.sp_context(teams)
    actual = [t["actual_2025"] for t in teams]
    baseline_pred = [v4.baseline(t, sc) for t in teams]
    baseline = v4.metrics(baseline_pred, actual)

    print("=" * 78)
    print("PROJECT GRIDIRON PORTAL-WEIGHT STRESS TEST")
    print("=" * 78)
    print(f"Teams tested: {len(teams)}")
    print(f"Adjustment cap: +/-{v4.MAX_ADJ:.1f} points")
    print(f"Baseline: corr={baseline['correlation']:.4f}, MAE={baseline['mae']:.3f}, RMSE={baseline['rmse']:.3f}")

    total = 1
    for k in v4.FEATURES:
        total *= len(GRIDS[k])
    print(f"Parameter combinations: {total:,}")
    print("Portal ranges: TT -3.0 to +5.0; TP -3.0 to +5.0 pts/std")

    results = []
    for vals in product(*(GRIDS[k] for k in v4.FEATURES)):
        weights = dict(zip(v4.FEATURES, vals))
        m = v4.evaluate(teams, sc, fc, weights)
        m["improves_all"] = v4.improves(m, baseline)
        results.append(m)

    valid = [m for m in results if m["improves_all"]]
    print(f"Models improving all three baseline metrics: {len(valid):,}")

    # Different objectives answer different questions. Point-error metrics get
    # explicit treatment because production use is ultimately game prediction.
    rankings = {
        "LOWEST MAE": sorted(valid, key=lambda m: (m["mae"], m["rmse"], -m["correlation"], m["average_absolute_adjustment"])),
        "LOWEST RMSE": sorted(valid, key=lambda m: (m["rmse"], m["mae"], -m["correlation"], m["average_absolute_adjustment"])),
        "HIGHEST CORRELATION": sorted(valid, key=lambda m: (-m["correlation"], m["mae"], m["rmse"], m["average_absolute_adjustment"])),
    }
    for title, rows in rankings.items():
        print("\n" + title)
        print("-" * 78)
        for i, m in enumerate(rows[:15], 1):
            print(f"{i}. {fmt(m)}")

    # Pareto frontier: no other valid model is at least as good on corr, MAE,
    # and RMSE and strictly better on one. This avoids choosing by one metric.
    frontier = []
    for m in valid:
        dominated = False
        for n in valid:
            if n is m:
                continue
            no_worse = (n["correlation"] >= m["correlation"] and n["mae"] <= m["mae"] and n["rmse"] <= m["rmse"])
            strictly_better = (n["correlation"] > m["correlation"] or n["mae"] < m["mae"] or n["rmse"] < m["rmse"])
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.append(m)
    frontier.sort(key=lambda m: (m["mae"] + m["rmse"], -m["correlation"], m["average_absolute_adjustment"]))
    print("\nPARETO FRONTIER - TOP 25 BY POINT ERROR")
    print("-" * 78)
    print(f"Pareto models: {len(frontier)}")
    for i, m in enumerate(frontier[:25], 1):
        print(f"{i}. {fmt(m)}")

    # Portal-only slices make the core hypothesis easy to read while holding
    # the conservative V4 candidate's other weights fixed at RP=1,QB=0,Coach=1.
    portal_slice = [m for m in results if m["weights"]["returning_production"] == 1.0 and m["weights"]["qb_continuity"] == 0.0 and m["weights"]["coaching"] == 1.0]
    portal_slice.sort(key=lambda m: (m["mae"], m["rmse"], -m["correlation"]))
    print("\nPORTAL STRESS SLICE - RP=1.00, QB=0.00, COACH=1.00")
    print("-" * 78)
    for i, m in enumerate(portal_slice[:25], 1):
        print(f"{i}. {fmt(m)}")

    # Explicit wrong-way check. If positive portal signal is real, reversing it
    # should materially degrade performance.
    print("\nDIRECTIONALITY SANITY CHECK")
    print("-" * 78)
    checks = [
        {"returning_production": 1.0, "transfer_talent": 1.0, "transfer_production": 1.0, "qb_continuity": 0.0, "coaching": 1.0},
        {"returning_production": 1.0, "transfer_talent": 3.0, "transfer_production": 3.0, "qb_continuity": 0.0, "coaching": 1.0},
        {"returning_production": 1.0, "transfer_talent": -1.0, "transfer_production": -1.0, "qb_continuity": 0.0, "coaching": 1.0},
        {"returning_production": 1.0, "transfer_talent": -3.0, "transfer_production": -3.0, "qb_continuity": 0.0, "coaching": 1.0},
    ]
    for w in checks:
        print(fmt(v4.evaluate(teams, sc, fc, w)))

    # Boundary warning is the key interpretation aid: if best point-error
    # models still sit at +5, the search needs expansion rather than freezing.
    best_mae = rankings["LOWEST MAE"][0]
    best_rmse = rankings["LOWEST RMSE"][0]
    print("\nBOUNDARY CHECK")
    print("-" * 78)
    for label, m in (("Best MAE", best_mae), ("Best RMSE", best_rmse)):
        w = m["weights"]
        tt_edge = w["transfer_talent"] == max(GRIDS["transfer_talent"])
        tp_edge = w["transfer_production"] == max(GRIDS["transfer_production"])
        print(f"{label}: TT={w['transfer_talent']:+.2f}{' [UPPER EDGE]' if tt_edge else ''}, TP={w['transfer_production']:+.2f}{' [UPPER EDGE]' if tp_edge else ''}")
    print("\nInterpretation: an upper-edge winner means do NOT freeze that portal weight yet.")


if __name__ == "__main__":
    analyze()
