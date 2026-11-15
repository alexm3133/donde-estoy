"""The session state machine, driven by simulated outings."""

import pytest

from app.eta import Terrain
from app.services.route import build_route
from app.services.tracker import Fix, Tracker, TrackerState

from .helpers import MOUNTAIN_PROFILE, north_of_start, simulate_run, straight_route

T0 = 1_700_000_000.0
EVEN = {Terrain.UPHILL: 1.7, Terrain.FLAT: 1.7, Terrain.DOWNHILL: 1.7}


def route_tracker(route, activity="run", state=None):
    return Tracker(state or TrackerState(), route=route, destination=route.end, activity=activity)


def point_tracker(destination_m=2000.0):
    return Tracker(
        TrackerState(), route=None, destination=north_of_start(destination_m), activity="run"
    )


def fix_at(meters, ts, **kwargs):
    lat, lon = north_of_start(meters)
    return Fix(lat=lat, lon=lon, ts=ts, **kwargs)


@pytest.fixture
def mountain():
    return build_route(straight_route(MOUNTAIN_PROFILE))


# -- a whole outing ----------------------------------------------------------------


def test_full_run_with_gps_noise_tracks_progress_and_arrives(mountain):
    tracker = route_tracker(mountain)
    factors = {Terrain.UPHILL: 1.4, Terrain.FLAT: 1.3, Terrain.DOWNHILL: 1.0}
    fixes = list(simulate_run(mountain, factors, noise_m=4.0))
    finish_ts = fixes[-1][0].ts
    errors = {}
    for fix, true_distance in fixes:
        tracker.process(fix)
        state = tracker.state
        if state.arrived_at is None:
            assert state.progress_m == pytest.approx(true_distance, abs=25)
            truth = finish_ts - fix.ts
            if truth > 120:
                errors[round(true_distance, -2)] = abs(state.eta["seconds"] - truth) / truth

    state = tracker.state
    assert state.arrived_at == pytest.approx(finish_ts, abs=30)
    assert state.eta["seconds"] == 0
    assert state.remaining["distance_m"] == 0
    assert state.distance_m == pytest.approx(10_000, rel=0.1)
    # Nearly all the time was spent moving and counted as such.
    assert state.moving_time_s == pytest.approx(finish_ts - T0, rel=0.1)
    # ETA accuracy improves as terrain gets calibrated (see test_eta_engine).
    assert errors[6000] < 0.12
    assert errors[9000] < 0.12
    assert state.eta["confidence"] == "high"


def test_state_survives_json_round_trip_between_fixes(mountain):
    """The API stores the state as JSON after every batch."""
    import json

    continuous = route_tracker(mountain)
    state = TrackerState()
    for fix, _ in simulate_run(mountain, EVEN, noise_m=3.0):
        continuous.process(fix)
        tracker = route_tracker(mountain, state=state)
        tracker.process(fix)
        state = TrackerState.from_dict(json.loads(json.dumps(tracker.state.to_dict())))
    assert state.arrived_at == continuous.state.arrived_at
    assert state.moving_time_s == pytest.approx(continuous.state.moving_time_s)


def test_a_long_break_does_not_ruin_the_pace_estimate(mountain):
    """Stopping 10 min for a sandwich must not make the runner look slow."""
    paused = {"done": False}

    def lunch(distance):
        if distance >= 3000 and not paused["done"]:
            paused["done"] = True
            return 600.0
        return 0.0

    with_break = route_tracker(mountain)
    without = route_tracker(mountain)
    for fix, distance in simulate_run(mountain, EVEN, pause=lunch):
        with_break.process(fix)
        if distance >= 6000:
            break
    for fix, distance in simulate_run(mountain, EVEN):
        without.process(fix)
        if distance >= 6000:
            break
    assert with_break.state.eta["seconds"] == pytest.approx(without.state.eta["seconds"], rel=0.03)
    assert with_break.state.moving_time_s == pytest.approx(without.state.moving_time_s, rel=0.03)


# -- movement / stopped ----------------------------------------------------------------


def test_last_moved_at_freezes_while_standing_still():
    tracker = point_tracker()
    tracker.process(fix_at(0, T0))
    tracker.process(fix_at(40, T0 + 20))
    assert tracker.state.last_moved_at == T0 + 20
    # GPS jitter of a few metres while standing is not movement.
    for i, wobble in enumerate([42, 37, 44, 39, 41]):
        tracker.process(fix_at(wobble, T0 + 30 + i * 10))
    assert tracker.state.last_moved_at == T0 + 20
    tracker.process(fix_at(80, T0 + 100))
    assert tracker.state.last_moved_at == T0 + 100


def test_inaccurate_fix_needs_to_clear_its_own_error_radius():
    tracker = point_tracker()
    tracker.process(fix_at(0, T0, accuracy=5))
    tracker.process(fix_at(25, T0 + 10, accuracy=35))  # 25 m away but ±35 m
    assert tracker.state.last_moved_at == T0
    tracker.process(fix_at(25, T0 + 20, accuracy=5))
    assert tracker.state.last_moved_at == T0 + 20


# -- bad data ----------------------------------------------------------------


def test_rejects_low_accuracy_and_out_of_order_fixes():
    tracker = point_tracker()
    assert tracker.process(fix_at(0, T0, accuracy=10))
    assert not tracker.process(fix_at(10, T0 + 5, accuracy=500))
    assert not tracker.process(fix_at(10, T0))  # same timestamp
    assert not tracker.process(fix_at(10, T0 - 30))  # older
    assert tracker.state.last_fix["ts"] == T0


def test_a_single_gps_teleport_is_ignored(mountain):
    tracker = route_tracker(mountain)
    tracker.process(fix_at(0, T0))
    tracker.process(fix_at(15, T0 + 5))
    assert not tracker.process(fix_at(5000, T0 + 10))  # 5 km in 5 s
    assert tracker.process(fix_at(30, T0 + 15))
    assert tracker.state.progress_m == pytest.approx(30, abs=5)


def test_a_persistent_new_location_is_eventually_believed(mountain):
    """If the 'teleport' keeps being confirmed, the earlier fix was the lie."""
    tracker = route_tracker(mountain)
    tracker.process(fix_at(0, T0))
    results = [tracker.process(fix_at(6000 + i * 10, T0 + 5 + i * 5)) for i in range(5)]
    assert results == [False, False, False, True, True]
    assert tracker.state.progress_m == pytest.approx(6040, abs=10)


def test_teleports_do_not_pollute_the_calibration(mountain):
    tracker = route_tracker(mountain)
    tracker.process(fix_at(0, T0))
    for i in range(5):
        tracker.process(fix_at(6000 + i * 10, T0 + 5 + i * 5))
    assert tracker.calibration.overall_factor == pytest.approx(1.7, rel=0.05)


# -- arrival ----------------------------------------------------------------


def test_arrives_at_a_point_destination():
    tracker = point_tracker(destination_m=500)
    for i in range(0, 51):
        tracker.process(fix_at(i * 10, T0 + i * 4))
        if tracker.state.arrived_at:
            break
    assert tracker.state.arrived_at is not None
    assert i * 10 >= 470  # only within the 30 m arrival radius
    # Further fixes are ignored once arrived.
    assert not tracker.process(fix_at(600, T0 + 1000))


def test_point_destination_eta_uses_observed_speed_and_detour():
    tracker = point_tracker(destination_m=5000)
    # 3 m/s for a few minutes.
    for i in range(80):
        tracker.process(fix_at(i * 15, T0 + i * 5))
    remaining_straight = 5000 - 79 * 15
    assert tracker.state.remaining["distance_m"] == pytest.approx(
        remaining_straight * 1.3, rel=0.01
    )
    assert tracker.state.eta["seconds"] == pytest.approx(remaining_straight * 1.3 / 3.0, rel=0.12)


def test_loop_route_does_not_arrive_at_the_start():
    out = straight_route([(0, 500), (1000, 600)])
    loop = build_route(out + out[-2::-1])
    tracker = route_tracker(loop)
    tracker.process(fix_at(0, T0))
    tracker.process(fix_at(5, T0 + 5))
    assert tracker.state.arrived_at is None
    assert tracker.state.progress_m < 50
    assert tracker.state.remaining["distance_m"] > 1900


def test_passing_near_the_finish_while_off_route_is_not_arrival(mountain):
    tracker = route_tracker(mountain)
    lat, lon = north_of_start(10_000, east_m=90)  # level with the finish, 90 m to the side
    tracker.process(Fix(lat=lat, lon=lon, ts=T0))
    assert tracker.state.arrived_at is None


# -- off route ----------------------------------------------------------------


def test_off_route_adds_the_way_back_and_pauses_calibration(mountain):
    tracker = route_tracker(mountain)
    on_route = route_tracker(mountain)
    lat, lon = north_of_start(1000, east_m=300)
    tracker.process(Fix(lat=lat, lon=lon, ts=T0))
    on_route.process(fix_at(1000, T0))
    assert tracker.state.offset_m == pytest.approx(300, abs=5)
    assert tracker.state.remaining["distance_m"] == pytest.approx(
        on_route.state.remaining["distance_m"] + 300, abs=10
    )
    # Wandering parallel to the route, 300 m away, teaches us nothing.
    for i in range(1, 30):
        lat, lon = north_of_start(1000 + i * 20, east_m=300)
        tracker.process(Fix(lat=lat, lon=lon, ts=T0 + i * 5))
    assert tracker.calibration.total_observed_s == 0
