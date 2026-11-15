"""ETA estimation from remaining legs and a calibration."""

import pytest

from app.eta import Leg, Terrain, estimate, model_seconds, new_calibration, tobler_speed_ms
from app.services.route import build_route

from .helpers import MOUNTAIN_PROFILE, simulate_run, straight_route


def test_empty_path_takes_no_time():
    result = estimate([], new_calibration("run"))
    assert result.seconds == 0
    assert result.distance_m == 0


def test_flat_run_at_default_pace():
    result = estimate([Leg(10_000, 0)], new_calibration("run"))
    expected = 10_000 / (1.7 * tobler_speed_ms(0))
    assert result.seconds == pytest.approx(expected)
    assert 60 < result.seconds / 60 < 80  # ~70 min for 10 km: sane for trail running


def test_hiker_is_slower_than_runner():
    legs = [Leg(5000, 300)]
    assert (
        estimate(legs, new_calibration("hike")).seconds
        > estimate(legs, new_calibration("run")).seconds
    )


def test_climbing_costs_time_that_distance_alone_does_not_show():
    """The whole point of the app: 5 km with 800 m up is not 5 km flat."""
    calibration = new_calibration("run")
    flat = estimate([Leg(5000, 0)], calibration).seconds
    steep_up = estimate([Leg(5000, 800)], calibration).seconds
    steep_down = estimate([Leg(5000, -800)], calibration).seconds
    assert steep_up > 1.5 * flat
    assert flat < steep_down < steep_up


def test_totals_report_distance_ascent_and_descent():
    result = estimate([Leg(1000, 120), Leg(500, 0), Leg(800, -90)], new_calibration("run"))
    assert result.distance_m == 2300
    assert result.ascent_m == 120
    assert result.descent_m == 90


def test_zero_length_legs_are_skipped():
    calibration = new_calibration("run")
    assert estimate([Leg(0, 50), Leg(100, 0)], calibration).seconds == pytest.approx(
        estimate([Leg(100, 0)], calibration).seconds
    )


def test_uses_the_factor_of_each_terrain():
    calibration = new_calibration("run")
    for _ in range(300):
        calibration.observe([Leg(50, 10)], model_seconds(Leg(50, 10)) / 1.0)  # slow climber
        calibration.observe([Leg(50, 0)], model_seconds(Leg(50, 0)) / 2.0)  # quick on flat
    up = estimate([Leg(1000, 200)], calibration).seconds
    flat = estimate([Leg(1000, 0)], calibration).seconds
    assert up == pytest.approx(model_seconds(Leg(1000, 200)) / 1.0, rel=0.1)
    assert flat == pytest.approx(model_seconds(Leg(1000, 0)) / 2.0, rel=0.1)


def test_confidence_grows_and_band_narrows_with_data():
    calibration = new_calibration("run")
    legs = [Leg(5000, 100)]
    before = estimate(legs, calibration)
    assert before.confidence == "low"
    assert before.low_seconds < before.seconds < before.high_seconds

    leg = Leg(50, 0)
    while calibration.total_observed_s < 200:
        calibration.observe([leg], model_seconds(leg) / 1.7)
    middle = estimate(legs, calibration)
    assert middle.confidence == "medium"

    while calibration.total_observed_s < 1000:
        calibration.observe([leg], model_seconds(leg) / 1.7)
    after = estimate(legs, calibration)
    assert after.confidence == "high"

    def width(e):
        return (e.high_seconds - e.low_seconds) / e.seconds

    assert width(before) > width(middle) > width(after)
    assert width(after) == pytest.approx(0.2)


# --- end to end: does the engine actually predict a mountain run? ------------


def run_and_record(route, factors, activity="run"):
    """Simulate a perfect-GPS run, calibrating every 50 m like the tracker does.

    Returns ``[(distance, time_left_truth, time_left_predicted), ...]``.
    """
    calibration = new_calibration(activity)
    fixes = list(simulate_run(route, factors))
    finish_ts = fixes[-1][0].ts
    samples = []
    anchor_distance, anchor_ts = 0.0, fixes[0][0].ts
    for fix, distance in fixes:
        if distance - anchor_distance >= 50:
            calibration.observe(route.legs_between(anchor_distance, distance), fix.ts - anchor_ts)
            anchor_distance, anchor_ts = distance, fix.ts
        predicted = estimate(route.legs_between(distance, route.total_m), calibration).seconds
        samples.append((distance, finish_ts - fix.ts, predicted))
    return samples


def sample_at(samples, distance):
    return next(s for s in samples if s[0] >= distance)


def test_uncalibrated_eta_is_already_reasonable_for_a_typical_runner():
    route = build_route(straight_route(MOUNTAIN_PROFILE))
    typical = {Terrain.UPHILL: 1.7, Terrain.FLAT: 1.7, Terrain.DOWNHILL: 1.7}
    _, truth, predicted = run_and_record(route, typical)[0]
    assert predicted == pytest.approx(truth, rel=0.05)


def test_eta_converges_for_a_runner_unlike_the_default():
    """Slow, with terrain-specific strengths: the engine must learn them."""
    route = build_route(straight_route(MOUNTAIN_PROFILE))
    factors = {Terrain.UPHILL: 1.5, Terrain.FLAT: 1.2, Terrain.DOWNHILL: 0.9}
    samples = run_and_record(route, factors)

    _, truth0, predicted0 = samples[0]
    assert abs(predicted0 - truth0) / truth0 > 0.2  # the default is well off...

    # ...after the flat approach, the flat pace is known and extrapolated.
    _, truth, predicted = sample_at(samples, 1900)
    assert abs(predicted - truth) / truth < abs(predicted0 - truth0) / truth0

    # Half-way up the climb we have seen flat and uphill, but never downhill.
    _, truth, predicted = sample_at(samples, 3500)
    assert predicted == pytest.approx(truth, rel=0.25)

    # Early in the descent all three terrains are calibrated.
    _, truth, predicted = sample_at(samples, 6000)
    assert predicted == pytest.approx(truth, rel=0.10)

    # And near the end it is tight.
    _, truth, predicted = sample_at(samples, 9000)
    assert predicted == pytest.approx(truth, rel=0.08)


def test_beats_a_naive_constant_pace_eta_on_a_summit_route():
    """Flat approach then a big climb: 'distance / average speed so far'
    (what flat-land ETAs do) is badly optimistic at the foot of the climb."""
    route = build_route(straight_route([(0, 800), (4000, 800), (8000, 1700)]))
    factors = {Terrain.UPHILL: 1.6, Terrain.FLAT: 1.6, Terrain.DOWNHILL: 1.6}
    samples = run_and_record(route, factors)

    distance, truth, predicted = sample_at(samples, 3900)
    elapsed = (samples[0][1]) - truth
    naive = (route.total_m - distance) / (distance / elapsed)

    assert predicted == pytest.approx(truth, rel=0.08)
    assert naive < 0.6 * truth  # naive says "almost there"; reality: a long climb
