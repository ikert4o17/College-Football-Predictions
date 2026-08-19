"""Production configuration for Project Gridiron preseason model V4.

Frozen after the 2024-2025 multi-year validation. The selected point-error
winner improved correlation, MAE, and RMSE in both validation seasons.

Multi-year validation summary:
- 3,500 shared weight combinations tested
- 713 combinations improved correlation, MAE, and RMSE in both seasons
- Baseline average: corr=0.6211, MAE=8.919, RMSE=10.992
- V4 average:       corr=0.6278, MAE=8.677, RMSE=10.802
- Average MAE improvement: 0.242 points
- Average RMSE improvement: 0.190 points
- Average absolute adjustment: 1.82 points

Transfer production remains in the feature pipeline even though its frozen V4
coefficient is zero, so it can be re-tested as additional seasons are added.
"""

PRESEASON_V4_WEIGHTS = {
    "returning_production": 2.00,
    "transfer_talent": 0.50,
    "transfer_production": 0.00,
    "qb_continuity": -0.50,
    "coaching": 2.00,
}

PRESEASON_V4_MAX_ADJUSTMENT = 6.0

PRESEASON_V4_VALIDATION = {
    "seasons": [2024, 2025],
    "parameter_combinations_tested": 3500,
    "robust_models": 713,
    "baseline_average": {
        "correlation": 0.6211,
        "mae": 8.919,
        "rmse": 10.992,
    },
    "selected_model_average": {
        "correlation": 0.6278,
        "mae": 8.677,
        "rmse": 10.802,
        "average_absolute_adjustment": 1.82,
    },
}
