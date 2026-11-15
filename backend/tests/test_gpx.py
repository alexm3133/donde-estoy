"""GPX parsing, including hostile input."""

import pytest

from app.services.gpx import GpxError, parse_gpx

from .helpers import gpx_document


def test_parses_track_points_with_elevation():
    name, points = parse_gpx(
        gpx_document([(42.0, 1.5, 1000.0), (42.001, 1.5, 1010.5)], "Pedraforca")
    )
    assert name == "Pedraforca"
    assert points == [(42.0, 1.5, 1000.0), (42.001, 1.5, 1010.5)]


def test_elevation_is_optional():
    _, points = parse_gpx(gpx_document([(42.0, 1.5, None), (42.001, 1.5, None)]))
    assert points == [(42.0, 1.5, None), (42.001, 1.5, None)]


def test_falls_back_to_route_points_and_ignores_namespaces():
    document = b"""<gpx version="1.0">
      <rte><rtept lat="42.0" lon="1.5"/><rtept lat="42.1" lon="1.6"><ele>900</ele></rtept></rte>
    </gpx>"""
    _, points = parse_gpx(document)
    assert points == [(42.0, 1.5, None), (42.1, 1.6, 900.0)]


def test_prefers_the_recorded_track_over_route_waypoints():
    document = b"""<gpx>
      <rte><rtept lat="1" lon="1"/><rtept lat="2" lon="2"/></rte>
      <trk><trkseg><trkpt lat="42.0" lon="1.5"/><trkpt lat="42.1" lon="1.5"/></trkseg></trk>
    </gpx>"""
    assert parse_gpx(document)[1][0] == (42.0, 1.5, None)


def test_joins_multiple_segments_in_order():
    document = b"""<gpx><trk>
      <trkseg><trkpt lat="42.0" lon="1.5"/></trkseg>
      <trkseg><trkpt lat="42.1" lon="1.5"/><trkpt lat="42.2" lon="1.5"/></trkseg>
    </trk></gpx>"""
    assert [p[0] for p in parse_gpx(document)[1]] == [42.0, 42.1, 42.2]


def test_skips_malformed_points():
    document = b"""<gpx><trk><trkseg>
      <trkpt lat="42.0" lon="1.5"/>
      <trkpt lat="oops" lon="1.5"/>
      <trkpt lat="95.0" lon="1.5"/>
      <trkpt lon="1.5"/>
      <trkpt lat="42.1" lon="1.5"><ele>high</ele></trkpt>
    </trkseg></trk></gpx>"""
    assert parse_gpx(document)[1] == [(42.0, 1.5, None), (42.1, 1.5, None)]


@pytest.mark.parametrize(
    ("document", "code"),
    [
        (b"this is not xml", "gpx_invalid"),
        (b"", "gpx_invalid"),
        (b"<kml></kml>", "gpx_invalid"),
        (b"<gpx></gpx>", "gpx_no_points"),
        (b'<gpx><wpt lat="42" lon="1"/></gpx>', "gpx_no_points"),
        (b'<gpx><trk><trkseg><trkpt lat="42" lon="1"/></trkseg></trk></gpx>', "gpx_no_points"),
    ],
)
def test_rejects_unusable_files(document, code):
    with pytest.raises(GpxError) as error:
        parse_gpx(document)
    assert error.value.code == code


def test_refuses_entity_expansion_attacks():
    bomb = b"""<?xml version="1.0"?>
    <!DOCTYPE gpx [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>
    <gpx><trk><name>&b;</name></trk></gpx>"""
    with pytest.raises(GpxError) as error:
        parse_gpx(bomb)
    assert error.value.code == "gpx_invalid"
