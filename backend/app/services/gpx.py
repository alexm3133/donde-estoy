"""GPX parsing.

Only what we need: the ordered list of points of the track (or, failing
that, of the planned route). Parsed with ``defusedxml`` because the file is
untrusted user input (protects against entity-expansion attacks).
"""

from __future__ import annotations

from xml.etree.ElementTree import Element

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from .route import RawPoint


class GpxError(ValueError):
    """The file is not a GPX we can use. ``code`` is a stable machine id."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _local(tag: str) -> str:
    """Strip the XML namespace: ``{http://...}trkpt`` -> ``trkpt``."""
    return tag.rsplit("}", 1)[-1]


def parse_gpx(content: bytes) -> tuple[str | None, list[RawPoint]]:
    """Return ``(name, points)`` from a GPX document.

    Track points (``trkpt``) win over route points (``rtept``): a recorded
    track follows the actual trail, a route is often just a few waypoints.
    """
    try:
        root = SafeET.fromstring(content)
    except (SafeET.ParseError, DefusedXmlException, ValueError) as exc:
        raise GpxError("gpx_invalid") from exc
    if _local(root.tag) != "gpx":
        raise GpxError("gpx_invalid")

    name: str | None = None
    track_points: list[RawPoint] = []
    route_points: list[RawPoint] = []
    for element in root.iter():
        tag = _local(element.tag)
        if tag == "name" and name is None and element.text:
            name = element.text.strip()[:120] or None
        elif tag == "trkpt":
            _append_point(track_points, element)
        elif tag == "rtept":
            _append_point(route_points, element)

    points = track_points or route_points
    if len(points) < 2:
        raise GpxError("gpx_no_points")
    return name, points


def _append_point(points: list[RawPoint], element: Element) -> None:
    try:
        lat = float(element.attrib["lat"])
        lon = float(element.attrib["lon"])
    except (KeyError, ValueError):
        return  # skip malformed points rather than rejecting the whole file
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return
    elevation: float | None = None
    for child in element:
        if _local(child.tag) == "ele" and child.text:
            try:
                elevation = float(child.text)
            except ValueError:
                elevation = None
            break
    points.append((lat, lon, elevation))
