"""Small geodesy helpers. Accurate to well under 1 % at trail scales."""

from __future__ import annotations

import math

EARTH_RADIUS_M = 6_371_008.8
METERS_PER_DEGREE = EARTH_RADIUS_M * math.pi / 180.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def to_local_xy(
    lat: float, lon: float, origin_lat: float, origin_lon: float
) -> tuple[float, float]:
    """Project onto a flat plane (metres) centred on ``origin``.

    Equirectangular approximation: fine for the few kilometres around a point
    that we use it for (snapping a GPS fix to the route).
    """
    x = (lon - origin_lon) * METERS_PER_DEGREE * math.cos(math.radians(origin_lat))
    y = (lat - origin_lat) * METERS_PER_DEGREE
    return x, y
