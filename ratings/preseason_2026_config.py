"""Frozen Project Gridiron 2026 preseason configuration.

Decision: 2026 preseason SP+ mapped to the Project Gridiron scale plus the
Balanced Light offseason overlay selected on 2026-08-24.
"""

PRESEASON_2026_MODEL_VERSION = "2026_preseason_balanced_light"
PRESEASON_2026_WEIGHTS = {
    "returning_production": 1.25,
    "transfer_talent": 1.00,
    "qb_continuity": -0.25,
    "coaching": 0.50,
}
PRESEASON_2026_MAX_ADJUSTMENT = 4.0
PRESEASON_2026_ANCHOR = "2026 preseason SP+ mapped to 2025 Project Gridiron scale"
