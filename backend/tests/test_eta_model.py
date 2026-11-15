"""Tobler's hiking function and terrain classification."""

import pytest

from app.eta import Leg, Terrain, classify, model_seconds, tobler_speed_ms


def kmh(grade: float) -> float:
    return tobler_speed_ms(grade) * 3.6


def test_flat_speed_is_about_five_kmh():
    assert kmh(0.0) == pytest.approx(5.04, abs=0.01)


def test_fastest_on_a_gentle_descent():
    assert kmh(-0.05) == pytest.approx(6.0)
    assert all(kmh(-0.05) > kmh(g) for g in (-0.3, -0.1, 0.0, 0.1, 0.3))


def test_speed_drops_as_slopes_steepen_both_ways():
    climbs = [kmh(g) for g in (0.0, 0.1, 0.2, 0.3, 0.4)]
    descents = [kmh(g) for g in (-0.05, -0.15, -0.25, -0.35)]
    assert climbs == sorted(climbs, reverse=True)
    assert descents == sorted(descents, reverse=True)


def test_uphill_is_slower_than_the_same_slope_downhill():
    assert kmh(0.2) < kmh(-0.2)


def test_extreme_grades_are_clamped():
    assert tobler_speed_ms(5.0) == tobler_speed_ms(0.6)
    assert tobler_speed_ms(-5.0) == tobler_speed_ms(-0.6)
    assert tobler_speed_ms(0.6) > 0


@pytest.mark.parametrize(
    ("grade", "terrain"),
    [
        (0.20, Terrain.UPHILL),
        (0.051, Terrain.UPHILL),
        (0.05, Terrain.FLAT),
        (0.0, Terrain.FLAT),
        (-0.05, Terrain.FLAT),
        (-0.051, Terrain.DOWNHILL),
        (-0.30, Terrain.DOWNHILL),
    ],
)
def test_classify(grade, terrain):
    assert classify(grade) is terrain


def test_leg_grade_and_zero_length():
    assert Leg(100, 10).grade == pytest.approx(0.1)
    assert Leg(0, 10).grade == 0.0
    assert model_seconds(Leg(0, 0)) == 0.0


def test_model_seconds_one_kilometre_flat():
    # 1 km at 5.036 km/h ≈ 715 s
    assert model_seconds(Leg(1000, 0)) == pytest.approx(714.8, abs=1)
