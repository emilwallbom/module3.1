"""Paper reference settings and explicitly separate full-size adaptations.

The full-size plant and footprint constraints are adaptations; see
docs/PAPER_ALIGNMENT.md. These constants describe the controller, not BARC.
"""
HORIZON = 12  # Paper comparison profiles.
ROBUST_HORIZON = 24  # Default full-size adaptation, not a paper parameter.
DT = 0.1
HISTORY_LAPS = 2
TERMINAL_SAMPLES_PER_LAP = 20
REGRESSION_NEIGHBORS = 80
REGRESSION_METRIC = (0.1, 1.0, 1.0)
REGRESSION_BANDWIDTH = 10.0
# Paper specifies a small input-rate cost but does not give its coefficients.
# These are full-size tuning choices, in control-step units (not seconds).
INPUT_RATE_WEIGHTS = (1.0, 0.01)
WARMUP_INPUT_NOISE_STD = (0.0003, 0.025)
ALGORITHM_REVISION = "racing-limits-lmpc-v3"
TRACK_OVERHANG_FRACTION = 0.5
DEFAULT_PROFILE = "robust-lmpc"
PROFILES = ("robust-lmpc", "paper-hard", "author-soft")
ROBUST_STEERING_RATE = 0.7
ROBUST_TIRE_UTILIZATION = 0.9
ROBUST_SLIP_PENALTY = 10000.
