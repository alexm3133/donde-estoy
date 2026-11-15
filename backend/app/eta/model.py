"""Terrain model: how fast does a person move on a given slope?

We use **Tobler's hiking function** (Tobler, 1993), an empirical curve that maps
slope to walking speed::

    speed_kmh = 6 * exp(-3.5 * |grade + 0.05|)

It peaks at 6 km/h on a gentle -5 % descent, gives ~5 km/h on the flat and
falls off symmetrically as the terrain gets steeper either way. Compared with
Naismith's rule ("1 h per 5 km plus 1 h per 600 m of ascent") it has two
advantages for us: it is continuous, and it also slows down *steep descents*,
which matters a lot on technical mountain trails.

The curve describes a generic walker. The actual athlete is modelled by a
multiplicative *pace factor* on top of it (see :mod:`app.eta.calibration`).

This module is pure maths — no I/O, no clock, no database.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

#: Slopes are clamped to +/- this grade (60 %). Beyond that people scramble
#: rather than walk, and the exponential would predict absurd times.
MAX_GRADE = 0.6

#: Grade above which a leg counts as uphill (and below the negative: downhill).
TERRAIN_GRADE_THRESHOLD = 0.05


class Terrain(StrEnum):
    """Coarse terrain classes used to calibrate the runner's pace."""

    UPHILL = "uphill"
    FLAT = "flat"
    DOWNHILL = "downhill"


@dataclass(frozen=True, slots=True)
class Leg:
    """A piece of path: horizontal distance plus net elevation change."""

    distance_m: float
    elevation_delta_m: float = 0.0

    @property
    def grade(self) -> float:
        """Rise over run (0.10 == 10 % uphill). Zero-length legs are flat."""
        if self.distance_m <= 0:
            return 0.0
        return self.elevation_delta_m / self.distance_m


def tobler_speed_ms(grade: float) -> float:
    """Tobler walking speed in metres/second for a given grade (rise/run)."""
    clamped = max(-MAX_GRADE, min(MAX_GRADE, grade))
    return 6.0 * math.exp(-3.5 * abs(clamped + 0.05)) / 3.6


def classify(grade: float) -> Terrain:
    """Bucket a grade into uphill / flat / downhill."""
    if grade > TERRAIN_GRADE_THRESHOLD:
        return Terrain.UPHILL
    if grade < -TERRAIN_GRADE_THRESHOLD:
        return Terrain.DOWNHILL
    return Terrain.FLAT


def model_seconds(leg: Leg) -> float:
    """Time the *reference walker* (pace factor 1.0) needs to cover ``leg``."""
    if leg.distance_m <= 0:
        return 0.0
    return leg.distance_m / tobler_speed_ms(leg.grade)
