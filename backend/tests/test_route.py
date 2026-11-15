"""Route building, measuring and snapping."""

import pytest

from app.services.route import RouteError, build_route

from .helpers import MOUNTAIN_PROFILE, north_of_start, straight_route


@pytest.fixture
def mountain():
    return build_route(straight_route(MOUNTAIN_PROFILE))


def test_measures_distance_and_climb(mountain):
    assert mountain.total_m == pytest.approx(10_000, rel=0.005)
    ascent, descent = mountain.climb_totals()
    assert ascent == pytest.approx(450, abs=10)
    assert descent == pytest.approx(450, abs=10)
    assert mountain.has_elevation


def test_resamples_to_even_spacing():
    # Wildly irregular input: 3 points over 5 km.
    route = build_route(
        [(*north_of_start(0), 100.0), (*north_of_start(10), 100.0), (*north_of_start(5000), 600.0)]
    )
    gaps = [b - a for a, b in zip(route.dists, route.dists[1:], strict=False)]
    assert max(gaps) == pytest.approx(25, abs=1)
    assert min(gaps) == pytest.approx(25, abs=1)
    assert route.elevation_at(2500) == pytest.approx(350, abs=5)


def test_smoothing_removes_phantom_ascent():
    """±3 m of elevation jitter on a flat trail must not look like a climb."""
    points = []
    for i in range(500):
        lat, lon = north_of_start(i * 10)
        points.append((lat, lon, 1000.0 + (3 if i % 2 else -3)))
    ascent, descent = build_route(points).climb_totals()
    raw_ascent = 6 * 250
    assert ascent < raw_ascent * 0.1
    assert descent < raw_ascent * 0.1


def test_missing_elevation():
    flat = build_route([(*north_of_start(0), None), (*north_of_start(1000), None)])
    assert not flat.has_elevation
    assert flat.climb_totals() == (0, 0)

    # Partial gaps are filled from neighbours.
    partial = build_route(
        [(*north_of_start(0), None), (*north_of_start(500), 800.0), (*north_of_start(1000), None)]
    )
    assert partial.has_elevation
    assert partial.elevation_at(0) == pytest.approx(800)


@pytest.mark.parametrize(
    "points",
    [
        [],
        [(42.0, 1.5, 0.0)],
        [(42.0, 1.5, 0.0), (42.0, 1.5, 0.0)],  # same spot twice
        [(*north_of_start(0), 0.0), (*north_of_start(3), 0.0)],  # 3 m
    ],
)
def test_rejects_degenerate_routes(points):
    with pytest.raises(RouteError):
        build_route(points)


def test_legs_between_cover_exactly_the_requested_stretch(mountain):
    legs = mountain.legs_between(1990, 5010)
    assert sum(leg.distance_m for leg in legs) == pytest.approx(3020)
    assert sum(leg.elevation_delta_m for leg in legs) == pytest.approx(450, abs=10)
    assert mountain.legs_between(5000, 5000) == []
    assert mountain.legs_between(6000, 5000) == []
    # Clamped to the route.
    assert sum(leg.distance_m for leg in mountain.legs_between(-50, 1e9)) == pytest.approx(
        mountain.total_m
    )


def test_projects_a_nearby_fix_onto_the_route(mountain):
    lat, lon = north_of_start(3210, east_m=12)
    projection = mountain.project(lat, lon, hint_m=3100)
    assert projection.distance_m == pytest.approx(3210, abs=3)
    assert projection.offset_m == pytest.approx(12, abs=1)


def test_projection_without_hint_searches_everywhere(mountain):
    lat, lon = north_of_start(8765)
    assert mountain.project(lat, lon).distance_m == pytest.approx(8765, abs=3)


def test_projection_finds_runner_who_skipped_far_ahead(mountain):
    lat, lon = north_of_start(9000)
    projection = mountain.project(lat, lon, hint_m=1000)  # 8 km beyond the search window
    assert projection.distance_m == pytest.approx(9000, abs=3)


def out_and_back():
    """2 km north, then back along the very same path."""
    out = straight_route([(0, 500), (2000, 800)])
    return build_route(out + out[-2::-1])


def test_out_and_back_follows_the_outbound_leg_first():
    route = out_and_back()
    assert route.total_m == pytest.approx(4000, rel=0.01)
    progress = 0.0
    # Walk out: every fix is equally close to the outbound and return legs.
    for meters in range(0, 2001, 50):
        progress = route.project(*north_of_start(meters), hint_m=progress).distance_m
        assert progress == pytest.approx(meters, abs=20)
    # Walk back: progress keeps increasing past the turnaround.
    for meters in range(1950, -1, -50):
        progress = route.project(*north_of_start(meters), hint_m=progress).distance_m
        assert progress == pytest.approx(4000 - meters, abs=20)


def test_loop_start_is_not_mistaken_for_the_finish():
    route = out_and_back()  # starts and ends at the same point
    assert route.project(*north_of_start(0), hint_m=0.0).distance_m == pytest.approx(0, abs=5)


def test_round_trips_through_json_dict(mountain):
    from app.services.route import Route

    restored = Route.from_dict(mountain.to_dict())
    assert restored.total_m == pytest.approx(mountain.total_m, abs=0.1)
    assert restored.elevation_at(4321) == pytest.approx(mountain.elevation_at(4321), abs=0.1)
