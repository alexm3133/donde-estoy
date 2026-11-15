"""Learning the runner's pace from observations."""

import pytest

from app.eta import Leg, PaceCalibration, Terrain, model_seconds, new_calibration
from app.eta.calibration import HALF_LIFE_S

FLAT = Leg(50, 0)
UP = Leg(50, 10)  # 20 %
DOWN = Leg(50, -10)


def observe_at(calibration: PaceCalibration, leg: Leg, factor: float, times: int) -> None:
    """Feed ``times`` observations of a runner moving at ``factor`` x Tobler."""
    for _ in range(times):
        assert calibration.observe([leg], model_seconds(leg) / factor)


def test_starts_at_the_activity_default():
    run, hike = new_calibration("run"), new_calibration("hike")
    assert run.overall_factor == pytest.approx(1.7)
    assert hike.overall_factor == pytest.approx(0.9)
    assert all(run.factor(t) == pytest.approx(1.7) for t in Terrain)
    assert new_calibration("unicycle").overall_factor == 1.0


def test_converges_to_the_true_pace():
    calibration = new_calibration("run")
    observe_at(calibration, FLAT, 2.4, times=200)
    assert calibration.factor(Terrain.FLAT) == pytest.approx(2.4, rel=0.03)


def test_a_little_data_only_nudges_the_estimate():
    calibration = new_calibration("run")
    observe_at(calibration, FLAT, 3.0, times=2)  # ~24 s of data vs minutes of prior
    assert 1.7 < calibration.factor(Terrain.FLAT) < 2.1


def test_unseen_terrain_inherits_the_overall_pace():
    """Fast on the flat => assumed fast uphill too, until we see otherwise."""
    calibration = new_calibration("run")
    observe_at(calibration, FLAT, 2.5, times=200)
    assert calibration.factor(Terrain.UPHILL) == pytest.approx(2.5, rel=0.05)
    assert calibration.factor(Terrain.DOWNHILL) == pytest.approx(2.5, rel=0.05)


def test_learns_different_factors_per_terrain():
    """A strong climber who is cautious downhill."""
    calibration = new_calibration("run")
    for _ in range(60):
        observe_at(calibration, FLAT, 1.8, times=1)
        observe_at(calibration, UP, 2.4, times=1)
        observe_at(calibration, DOWN, 1.1, times=1)
    assert calibration.factor(Terrain.UPHILL) == pytest.approx(2.4, rel=0.08)
    assert calibration.factor(Terrain.FLAT) == pytest.approx(1.8, rel=0.08)
    assert calibration.factor(Terrain.DOWNHILL) == pytest.approx(1.1, rel=0.12)
    assert (
        calibration.factor(Terrain.UPHILL)
        > calibration.factor(Terrain.FLAT)
        > calibration.factor(Terrain.DOWNHILL)
    )


def test_recent_pace_outweighs_old_pace():
    """After fading, the estimate tracks the tired runner, not the fresh one."""
    calibration = new_calibration("run")
    fresh_s = tired_s = 0.0
    while fresh_s < 3 * HALF_LIFE_S:
        observe_at(calibration, FLAT, 2.2, times=1)
        fresh_s += model_seconds(FLAT) / 2.2
    while tired_s < 3 * HALF_LIFE_S:
        observe_at(calibration, FLAT, 1.4, times=1)
        tired_s += model_seconds(FLAT) / 1.4
    assert calibration.factor(Terrain.FLAT) == pytest.approx(1.4, rel=0.08)


@pytest.mark.parametrize(
    ("legs", "duration"),
    [
        ([Leg(1000, 0)], 5.0),  # 720 km/h: GPS teleport
        ([Leg(30, 0)], 3600.0),  # 30 m in an hour: not moving
        ([Leg(50, 0)], 0.0),
        ([Leg(50, 0)], -4.0),
        ([Leg(0, 0)], 10.0),
        ([], 10.0),
    ],
)
def test_implausible_observations_are_ignored(legs, duration):
    calibration = new_calibration("run")
    assert calibration.observe(legs, duration) is False
    assert calibration.total_observed_s == 0
    assert calibration.overall_factor == pytest.approx(1.7)


def test_observation_is_bucketed_by_average_slope():
    calibration = new_calibration("run")
    # Net +20 % even though one leg is flat.
    assert calibration.observe([Leg(25, 0), Leg(25, 10)], 30.0)
    assert calibration.stats[Terrain.UPHILL].observed_s == 30.0
    assert calibration.stats[Terrain.FLAT].observed_s == 0.0


def test_round_trips_through_json_dict():
    calibration = new_calibration("hike")
    observe_at(calibration, UP, 1.3, times=20)
    observe_at(calibration, DOWN, 0.8, times=5)
    restored = PaceCalibration.from_dict(calibration.to_dict())
    for terrain in Terrain:
        assert restored.factor(terrain) == pytest.approx(calibration.factor(terrain), rel=1e-3)
    assert restored.total_observed_s == pytest.approx(calibration.total_observed_s, abs=0.1)
