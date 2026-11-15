"""Live calibration of the runner's pace against the terrain model.

For each terrain class (uphill / flat / downhill) we learn a **pace factor**:
how many times faster than Tobler's reference walker this person is moving
*today, on this outing*. A factor of 2.0 on the flat means ~10 km/h.

How the estimate is built
-------------------------
Every observation is "the runner covered these legs in ``duration`` seconds".
We accumulate two sums per terrain class:

* ``model_s``    – seconds the reference walker would have needed
* ``observed_s`` – seconds the runner actually needed

The raw factor is simply ``model_s / observed_s``. Two refinements make it
behave well with little data:

1. **Shrinkage towards a prior.** With only a minute of data the raw ratio is
   noisy, so we blend it with a prior worth a few minutes of observation.
   The prior of each terrain class is the runner's *overall* factor (all
   classes pooled), and the prior of the overall factor is a per-activity
   default. So a runner who has only been seen on the flat, and was fast
   there, is assumed to also be fast uphill until proven otherwise.

2. **Recency weighting.** Within a terrain class, old observations decay with
   a half-life of ``HALF_LIFE_S`` seconds spent *on that terrain*, so the
   estimate follows fatigue (or a second wind) instead of averaging the whole
   day. What was learned on the last climb is not forgotten during a long
   descent — it only fades as newer climbing data replaces it.

The class is plain data + arithmetic and round-trips through ``to_dict`` /
``from_dict`` so it can be stored as JSON between position updates.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .model import Leg, Terrain, classify, model_seconds

#: How many seconds of observation the per-activity default is worth when
#: estimating the runner's overall factor...
OVERALL_PRIOR_WEIGHT_S = 180.0
#: ...and how many the overall factor is worth for a single terrain class.
TERRAIN_PRIOR_WEIGHT_S = 120.0
#: Half-life (in observed seconds on the same terrain) of past observations.
HALF_LIFE_S = 1500.0
#: Observations implying a factor outside this range are GPS glitches.
MIN_PLAUSIBLE_FACTOR = 0.15
MAX_PLAUSIBLE_FACTOR = 6.0


@dataclass(slots=True)
class TerrainStats:
    """Decayed sums for one terrain class."""

    model_s: float = 0.0
    observed_s: float = 0.0


@dataclass(slots=True)
class PaceCalibration:
    """Learned pace factors for one runner on one outing."""

    prior_factor: float
    stats: dict[Terrain, TerrainStats] = field(
        default_factory=lambda: {terrain: TerrainStats() for terrain in Terrain}
    )
    #: Total (undecayed) seconds of movement observed; drives confidence.
    total_observed_s: float = 0.0

    # -- learning ---------------------------------------------------------

    def observe(self, legs: Sequence[Leg], duration_s: float) -> bool:
        """Record that the runner covered ``legs`` in ``duration_s`` seconds.

        Returns ``False`` (and learns nothing) when the observation is
        degenerate or physically implausible.
        """
        distance = sum(leg.distance_m for leg in legs)
        if duration_s <= 0 or distance <= 0:
            return False

        reference_s = sum(model_seconds(leg) for leg in legs)
        implied_factor = reference_s / duration_s
        if not MIN_PLAUSIBLE_FACTOR <= implied_factor <= MAX_PLAUSIBLE_FACTOR:
            return False

        # The whole observation goes to the class of its *average* slope:
        # observations are short (tens of metres), so this is accurate enough
        # and keeps a clean "seconds in, seconds out" bookkeeping.
        net_climb = sum(leg.elevation_delta_m for leg in legs)
        bucket = self.stats[classify(net_climb / distance)]

        # Fade what we knew about this terrain by the time just spent on it.
        decay = 0.5 ** (duration_s / HALF_LIFE_S)
        bucket.model_s *= decay
        bucket.observed_s *= decay
        bucket.model_s += reference_s
        bucket.observed_s += duration_s
        self.total_observed_s += duration_s
        return True

    # -- reading ----------------------------------------------------------

    @property
    def overall_factor(self) -> float:
        """Pace factor pooled over all terrain, shrunk towards the default."""
        model_s = sum(s.model_s for s in self.stats.values())
        observed_s = sum(s.observed_s for s in self.stats.values())
        return (self.prior_factor * OVERALL_PRIOR_WEIGHT_S + model_s) / (
            OVERALL_PRIOR_WEIGHT_S + observed_s
        )

    def factor(self, terrain: Terrain) -> float:
        """Pace factor for one terrain class, shrunk towards the overall one."""
        terrain_stats = self.stats[terrain]
        return (self.overall_factor * TERRAIN_PRIOR_WEIGHT_S + terrain_stats.model_s) / (
            TERRAIN_PRIOR_WEIGHT_S + terrain_stats.observed_s
        )

    # -- persistence ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "prior_factor": self.prior_factor,
            "total_observed_s": round(self.total_observed_s, 1),
            "stats": {
                terrain.value: [round(s.model_s, 2), round(s.observed_s, 2)]
                for terrain, s in self.stats.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaceCalibration:
        calibration = cls(prior_factor=float(data["prior_factor"]))
        calibration.total_observed_s = float(data.get("total_observed_s", 0.0))
        for name, (model_s, observed_s) in data.get("stats", {}).items():
            calibration.stats[Terrain(name)] = TerrainStats(float(model_s), float(observed_s))
        return calibration
