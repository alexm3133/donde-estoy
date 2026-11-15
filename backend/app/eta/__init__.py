"""Mountain-aware ETA engine.

A self-contained, dependency-free package:

* :mod:`app.eta.model`        – Tobler's hiking function and terrain classes
* :mod:`app.eta.calibration`  – learns the runner's live pace per terrain class
* :mod:`app.eta.engine`       – turns remaining legs + calibration into an ETA

Nothing in here touches the network, the database or the clock, which keeps it
easy to test and to reason about.
"""

from .calibration import PaceCalibration
from .engine import DEFAULT_PACE_FACTOR, EtaEstimate, estimate, new_calibration
from .model import Leg, Terrain, classify, model_seconds, tobler_speed_ms

__all__ = [
    "DEFAULT_PACE_FACTOR",
    "EtaEstimate",
    "Leg",
    "PaceCalibration",
    "Terrain",
    "classify",
    "estimate",
    "model_seconds",
    "new_calibration",
    "tobler_speed_ms",
]
