"""ETA estimation: remaining path + calibrated pace -> time to arrival."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from .calibration import PaceCalibration
from .model import Leg, classify, model_seconds

Activity = Literal["run", "hike"]
Confidence = Literal["low", "medium", "high"]

#: Starting pace factors before we have seen the runner move.
#: Tobler's walker does ~5 km/h on the flat, so 1.7 is ~8.5 km/h (7:00 min/km),
#: a comfortable trail-running pace; 0.9 is a hiker with a pack and short stops.
DEFAULT_PACE_FACTOR: dict[str, float] = {"run": 1.7, "hike": 0.9}

#: Seconds of observed movement needed for each confidence level.
MEDIUM_CONFIDENCE_AFTER_S = 180.0
HIGH_CONFIDENCE_AFTER_S = 900.0

#: Relative half-width of the uncertainty band, before and after calibration.
UNCALIBRATED_UNCERTAINTY = 0.30
CALIBRATED_UNCERTAINTY = 0.10


@dataclass(frozen=True, slots=True)
class EtaEstimate:
    """Result of an ETA computation. All times are *moving* seconds from now."""

    seconds: float
    low_seconds: float
    high_seconds: float
    distance_m: float
    ascent_m: float
    descent_m: float
    confidence: Confidence


def new_calibration(activity: str) -> PaceCalibration:
    """Fresh calibration seeded with the default pace for ``activity``."""
    return PaceCalibration(prior_factor=DEFAULT_PACE_FACTOR.get(activity, 1.0))


def estimate(legs: Iterable[Leg], calibration: PaceCalibration) -> EtaEstimate:
    """Estimate the time needed to cover ``legs`` at the runner's pace.

    Each leg takes ``reference_time / pace_factor`` where the reference time
    comes from Tobler's function and the pace factor is the one learned for
    that leg's terrain class.
    """
    factors = {}
    seconds = distance = ascent = descent = 0.0
    for leg in legs:
        if leg.distance_m <= 0:
            continue
        terrain = classify(leg.grade)
        if terrain not in factors:
            factors[terrain] = calibration.factor(terrain)
        seconds += model_seconds(leg) / factors[terrain]
        distance += leg.distance_m
        if leg.elevation_delta_m > 0:
            ascent += leg.elevation_delta_m
        else:
            descent -= leg.elevation_delta_m

    observed = calibration.total_observed_s
    # The band narrows linearly as calibration data accumulates.
    progress = min(1.0, observed / HIGH_CONFIDENCE_AFTER_S)
    uncertainty = UNCALIBRATED_UNCERTAINTY + progress * (
        CALIBRATED_UNCERTAINTY - UNCALIBRATED_UNCERTAINTY
    )
    confidence: Confidence
    if observed >= HIGH_CONFIDENCE_AFTER_S:
        confidence = "high"
    elif observed >= MEDIUM_CONFIDENCE_AFTER_S:
        confidence = "medium"
    else:
        confidence = "low"

    return EtaEstimate(
        seconds=seconds,
        low_seconds=seconds * (1 - uncertainty),
        high_seconds=seconds * (1 + uncertainty),
        distance_m=distance,
        ascent_m=ascent,
        descent_m=descent,
        confidence=confidence,
    )
