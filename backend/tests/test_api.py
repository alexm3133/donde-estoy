"""HTTP + WebSocket API, end to end against a real (SQLite) database."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models import LiveSession, Position
from app.security import hash_token
from app.services.cleanup import purge_expired

from .conftest import Runner
from .helpers import MOUNTAIN_PROFILE, gpx_document, north_of_start, straight_route

ROUTE_POINTS = [list(p) for p in straight_route([(0, 500), (1000, 650)])]


def db_count(client, model) -> int:
    async def count():
        async with client.app.state.sessionmaker() as db:
            return (await db.execute(select(func.count()).select_from(model))).scalar_one()

    return client.portal.call(count)


def db_session_row(client, session_id) -> LiveSession | None:
    async def get():
        async with client.app.state.sessionmaker() as db:
            return await db.get(LiveSession, session_id)

    return client.portal.call(get)


# -- creating a session ----------------------------------------------------------


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_create_with_point_destination(client, runner):
    created = runner.created
    assert created["share_url"] == f"https://donde.example/s/{created['view_token']}"
    assert len(created["view_token"]) >= 22 and len(created["runner_token"]) >= 22
    assert created["view_token"] != created["runner_token"]
    snapshot = created["snapshot"]
    assert snapshot["state"] == "active"
    assert snapshot["runner_name"] == "Alex"
    assert snapshot["position"] is None and snapshot["eta"] is None
    assert snapshot["has_route"] is False
    assert snapshot["stall_alert_minutes"] == 10


def test_create_with_route_uses_its_end_as_destination(client):
    runner = Runner(client, route_points=ROUTE_POINTS, stall_alert_minutes=20, activity="hike")
    view = runner.view().json()
    assert view["has_route"] and view["activity"] == "hike"
    assert view["stall_alert_minutes"] == 20
    assert view["route"]["distance_m"] == pytest.approx(1000, rel=0.01)
    assert view["route"]["ascent_m"] == pytest.approx(150, abs=5)
    end_lat, end_lon = north_of_start(1000)
    assert view["destination"]["lat"] == pytest.approx(end_lat, abs=1e-5)
    assert view["destination"]["lon"] == pytest.approx(end_lon, abs=1e-5)
    assert len(view["route"]["points"][0]) == 4


def test_tokens_are_stored_only_as_hashes(client, runner):
    row = db_session_row(client, runner.id)
    assert row.view_token_hash == hash_token(runner.view_token)
    assert runner.view_token not in (row.view_token_hash, row.runner_token_hash)
    assert runner.created["runner_token"] not in (row.view_token_hash, row.runner_token_hash)


def test_session_lifetime_is_capped(client, settings):
    runner = Runner(client, duration_hours=1000)
    expires = datetime.fromisoformat(runner.created["expires_at"])
    assert expires - datetime.now(UTC) <= timedelta(hours=settings.max_session_hours)

    short = Runner(client, duration_hours=1)
    expires = datetime.fromisoformat(short.created["expires_at"])
    assert timedelta(minutes=59) < expires - datetime.now(UTC) <= timedelta(hours=1)


@pytest.mark.parametrize(
    "body",
    [
        {"runner_name": "Alex"},  # nowhere to go
        {"runner_name": "", "destination": {"lat": 42, "lon": 1}},
        {"runner_name": "   ", "destination": {"lat": 42, "lon": 1}},
        {"runner_name": "x" * 41, "destination": {"lat": 42, "lon": 1}},
        {"runner_name": "Alex", "destination": {"lat": 91, "lon": 1}},
        {"runner_name": "Alex", "destination": {"lat": 42, "lon": 181}},
        {"runner_name": "Alex", "destination": {"lat": 42, "lon": 1}, "stall_alert_minutes": 0},
        {"runner_name": "Alex", "destination": {"lat": 42, "lon": 1}, "activity": "fly"},
        {"runner_name": "Alex", "route_points": [[42, 1, 0]]},  # one point is no route
        {"runner_name": "Alex", "route_points": [[42, 1, 0], [42, 1, 0]]},
    ],
)
def test_create_validation(client, body):
    assert client.post("/api/sessions", json=body).status_code == 422


def test_create_is_rate_limited_per_client(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings.create_rate_limit_per_hour = 2
    body = {"runner_name": "Alex", "destination": {"lat": 42, "lon": 1}}
    with TestClient(create_app(settings)) as client:
        assert [client.post("/api/sessions", json=body).status_code for _ in range(3)] == [
            201,
            201,
            429,
        ]


# -- reporting positions ----------------------------------------------------------


def test_positions_update_the_viewer(client, runner):
    runner.move_to(0)
    result = runner.move_to(40)
    assert result["accepted"] == 1
    view = runner.view().json()
    lat, lon = north_of_start(40)
    assert view["position"]["lat"] == pytest.approx(lat)
    assert view["position"]["lon"] == pytest.approx(lon)
    assert view["progress"]["remaining_m"] == pytest.approx(1960 * 1.3, rel=0.01)
    assert view["eta"]["seconds"] > 0
    assert view["eta"]["confidence"] == "low"
    assert view["last_moved_at"] == view["position"]["ts"]
    assert view["track"] == [list(north_of_start(0)), [lat, lon]]


def test_route_session_reports_progress_and_climb_left(client):
    runner = Runner(client, route_points=ROUTE_POINTS)
    runner.move_to(0)
    snapshot = runner.move_to(400, after_s=120)["snapshot"]
    progress = snapshot["progress"]
    assert progress["done_m"] == pytest.approx(400, abs=5)
    assert progress["total_m"] == pytest.approx(1000, rel=0.01)
    assert progress["remaining_m"] == pytest.approx(600, abs=5)
    assert progress["remaining_ascent_m"] == pytest.approx(90, abs=5)
    assert progress["off_route"] is False


def test_batch_is_processed_in_time_order(client, runner):
    """A buffered batch (sent after regaining signal) may arrive shuffled."""
    base = datetime.now(UTC) - timedelta(minutes=10)
    batch = [
        {
            "lat": north_of_start(m)[0],
            "lon": north_of_start(m)[1],
            "ts": (base + timedelta(seconds=s)).isoformat(),
        }
        for m, s in [(80, 20), (0, 0), (40, 10)]
    ]
    response = runner.post(batch)
    assert response.json()["accepted"] == 3
    assert runner.view().json()["track"] == [list(north_of_start(m)) for m in (0, 40, 80)]


def test_bad_fixes_are_dropped_not_stored(client, runner):
    runner.move_to(0)
    assert runner.move_to(10, accuracy=900)["accepted"] == 0
    assert db_count(client, Position) == 1


def test_device_clock_skew_is_corrected(client, runner):
    """A phone whose clock is 2 h slow still yields current timestamps."""
    wrong_now = datetime.now(UTC) - timedelta(hours=2)
    lat, lon = north_of_start(0)
    response = runner.post(
        [{"lat": lat, "lon": lon, "ts": (wrong_now - timedelta(seconds=30)).isoformat()}],
        sent_at=wrong_now.isoformat(),
    )
    fix_time = datetime.fromisoformat(response.json()["snapshot"]["position"]["ts"])
    age = (datetime.now(UTC) - fix_time).total_seconds()
    assert age == pytest.approx(30, abs=5)


def test_future_timestamps_are_clamped_to_now(client, runner):
    lat, lon = north_of_start(0)
    future = datetime.now(UTC) + timedelta(hours=3)
    response = runner.post([{"lat": lat, "lon": lon, "ts": future.isoformat()}])
    fix_time = datetime.fromisoformat(response.json()["snapshot"]["position"]["ts"])
    assert fix_time <= datetime.now(UTC) + timedelta(seconds=10)


@pytest.mark.parametrize(
    "payload",
    [
        {"positions": []},
        {"positions": [{"lat": 99, "lon": 1, "ts": "2026-01-01T00:00:00Z"}]},
        {"positions": [{"lat": 42, "lon": 1}]},
        {"positions": [{"lat": 42, "lon": 1, "ts": "2026-01-01T00:00:00Z"}] * 501},
    ],
)
def test_position_validation(client, runner, payload):
    response = client.post(
        f"/api/sessions/{runner.id}/positions", json=payload, headers=runner.headers
    )
    assert response.status_code == 422


# -- auth ----------------------------------------------------------------


def test_runner_endpoints_need_the_runner_token(client, runner):
    lat, lon = north_of_start(0)
    body = {"positions": [{"lat": lat, "lon": lon, "ts": datetime.now(UTC).isoformat()}]}
    url = f"/api/sessions/{runner.id}/positions"
    assert client.post(url, json=body).status_code == 401
    assert client.post(url, json=body, headers={"Authorization": "Basic abc"}).status_code == 401
    assert client.post(url, json=body, headers={"Authorization": "Bearer nope"}).status_code == 404
    # The public view token must not grant runner powers.
    as_viewer = {"Authorization": f"Bearer {runner.view_token}"}
    assert client.post(url, json=body, headers=as_viewer).status_code == 404
    assert client.post(f"/api/sessions/{runner.id}/stop", headers=as_viewer).status_code == 404
    assert client.post(f"/api/sessions/{runner.id}/finish", headers=as_viewer).status_code == 404
    assert client.get(f"/api/sessions/{runner.id}", headers=as_viewer).status_code == 404
    assert db_count(client, Position) == 0


def test_one_runner_cannot_touch_another_session(client, runner):
    other = Runner(client)
    assert client.post(f"/api/sessions/{other.id}/stop", headers=runner.headers).status_code == 404
    assert other.view().json()["state"] == "active"


def test_viewer_cannot_use_session_id_or_runner_token_as_link(client, runner):
    assert client.get(f"/api/view/{runner.id}").status_code == 404
    assert client.get(f"/api/view/{runner.created['runner_token']}").status_code == 404
    assert client.get("/api/view/not-a-real-token").json() == {"detail": "link_not_found"}


def test_runner_can_resume_own_session(client):
    runner = Runner(client, route_points=ROUTE_POINTS)
    runner.move_to(100)
    own = client.get(f"/api/sessions/{runner.id}", headers=runner.headers).json()
    assert own["state"] == "active"
    assert own["route"]["distance_m"] == pytest.approx(1000, rel=0.01)
    assert own["position"] is not None


# -- arriving, finishing, stopping ----------------------------------------------------------


def test_arrival_is_detected_and_shortens_the_link_life(client, runner, settings):
    runner.move_to(1900)
    snapshot = runner.move_to(1990)["snapshot"]
    assert snapshot["state"] == "finished"
    assert snapshot["arrived_at"] is not None
    assert snapshot["eta"]["seconds"] == 0
    expires = datetime.fromisoformat(snapshot["expires_at"])
    grace = timedelta(minutes=settings.finished_grace_minutes)
    assert expires - datetime.now(UTC) <= grace
    # Later (buffered) fixes are accepted silently but change nothing.
    late = runner.move_to(1500)
    assert late["accepted"] == 0 and late["snapshot"]["state"] == "finished"
    assert runner.view().json()["state"] == "finished"


def test_manual_finish(client, runner):
    runner.move_to(500)
    response = client.post(f"/api/sessions/{runner.id}/finish", headers=runner.headers)
    assert response.json()["state"] == "finished"
    assert response.json()["arrived_at"] is not None
    # Idempotent.
    again = client.post(f"/api/sessions/{runner.id}/finish", headers=runner.headers)
    assert again.json()["arrived_at"] == response.json()["arrived_at"]


def test_stop_sharing_erases_location_data_immediately(client):
    runner = Runner(client, route_points=ROUTE_POINTS)
    runner.move_to(0)
    runner.move_to(50)
    assert db_count(client, Position) == 2

    response = client.post(f"/api/sessions/{runner.id}/stop", headers=runner.headers)
    assert response.json()["state"] == "ended"

    assert db_count(client, Position) == 0
    row = db_session_row(client, runner.id)
    assert row.route is None and row.tracker == {}
    assert row.dest_lat is None and row.dest_lon is None

    view = runner.view().json()
    assert view["state"] == "ended"
    assert view["position"] is None and view["destination"] is None
    assert view["route"] is None and view["track"] == []
    assert view["eta"] is None and view["progress"] is None

    # No more positions are accepted.
    lat, lon = north_of_start(60)
    late = runner.post([{"lat": lat, "lon": lon, "ts": datetime.now(UTC).isoformat()}])
    assert late.status_code == 410
    assert db_count(client, Position) == 0


# -- expiry ----------------------------------------------------------------


def expire(client, session_id):
    async def do():
        async with client.app.state.sessionmaker() as db:
            row = await db.get(LiveSession, session_id)
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await db.commit()

    client.portal.call(do)


def purge(client) -> int:
    return client.portal.call(purge_expired, client.app.state.sessionmaker, client.app.state.hub)


def test_expired_links_stop_working_even_before_the_purge(client, runner):
    runner.move_to(0)
    expire(client, runner.id)
    assert runner.view().status_code == 404
    lat, lon = north_of_start(10)
    response = runner.post([{"lat": lat, "lon": lon, "ts": datetime.now(UTC).isoformat()}])
    assert response.status_code == 404


def test_purge_deletes_expired_sessions_and_their_positions(client, runner):
    keeper = Runner(client)
    runner.move_to(0)
    runner.move_to(30)
    keeper.move_to(0)
    expire(client, runner.id)

    assert purge(client) == 1
    assert db_session_row(client, runner.id) is None
    assert db_count(client, Position) == 1  # only the live session's fix remains
    assert db_count(client, LiveSession) == 1
    assert keeper.view().status_code == 200
    assert purge(client) == 0


# -- live updates ----------------------------------------------------------------


def test_websocket_streams_snapshots(client, runner):
    with client.websocket_connect(f"/api/view/{runner.view_token}/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot" and first["data"]["position"] is None

        runner.move_to(0)
        update = ws.receive_json()
        assert update["type"] == "snapshot"
        assert update["data"]["position"]["lat"] == pytest.approx(north_of_start(0)[0])

        runner.move_to(60)
        assert ws.receive_json()["data"]["eta"]["seconds"] > 0

        client.post(f"/api/sessions/{runner.id}/stop", headers=runner.headers)
        ended = ws.receive_json()
        assert ended["data"]["state"] == "ended" and ended["data"]["position"] is None


def test_websocket_reaches_every_viewer_of_that_session_only(client, runner):
    other = Runner(client)
    with (
        client.websocket_connect(f"/api/view/{runner.view_token}/ws") as mum,
        client.websocket_connect(f"/api/view/{runner.view_token}/ws") as dad,
        client.websocket_connect(f"/api/view/{other.view_token}/ws") as stranger,
    ):
        for ws in (mum, dad, stranger):
            ws.receive_json()
        runner.move_to(0)
        assert mum.receive_json()["data"]["position"] is not None
        assert dad.receive_json()["data"]["position"] is not None
        other.move_to(700)
        # The stranger's first update is about *their* runner, not ours.
        assert stranger.receive_json()["data"]["position"]["lat"] == pytest.approx(
            north_of_start(700)[0]
        )


def test_websocket_rejects_unknown_links(client):
    from starlette.websockets import WebSocketDisconnect

    with (
        client.websocket_connect("/api/view/unknown/ws") as ws,
        pytest.raises(WebSocketDisconnect) as closed,
    ):
        ws.receive_json()
    assert closed.value.code == 4404


def test_websocket_is_told_when_the_session_expires(client, runner):
    from starlette.websockets import WebSocketDisconnect

    with client.websocket_connect(f"/api/view/{runner.view_token}/ws") as ws:
        ws.receive_json()
        expire(client, runner.id)
        purge(client)
        assert ws.receive_json() == {"type": "expired"}
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_hub_forgets_viewers_who_leave(client, runner):
    hub = client.app.state.hub
    with client.websocket_connect(f"/api/view/{runner.view_token}/ws") as ws:
        ws.receive_json()
        assert hub.viewer_count(runner.id) == 1
    for _ in range(50):
        if hub.viewer_count(runner.id) == 0:
            break
        client.portal.call(asyncio.sleep, 0.02)
    assert hub.viewer_count(runner.id) == 0


# -- GPX upload ----------------------------------------------------------------


def test_parse_gpx_then_create_session_from_it(client):
    gpx = gpx_document(straight_route(MOUNTAIN_PROFILE), "Volta al Pedraforca")
    response = client.post(
        "/api/routes/parse", files={"file": ("route.gpx", gpx, "application/gpx+xml")}
    )
    assert response.status_code == 200
    parsed = response.json()
    assert parsed["name"] == "Volta al Pedraforca"
    assert parsed["distance_m"] == pytest.approx(10_000, rel=0.01)
    assert parsed["ascent_m"] == pytest.approx(450, abs=10)
    assert parsed["has_elevation"] is True

    runner = Runner(client, route_points=parsed["raw_points"])
    assert runner.view().json()["route"]["distance_m"] == pytest.approx(parsed["distance_m"])
    assert db_count(client, LiveSession) == 1  # parsing itself stored nothing


def test_parse_gpx_errors(client, settings):
    def parse(content: bytes):
        return client.post("/api/routes/parse", files={"file": ("r.gpx", content, "text/xml")})

    assert parse(b"not xml").json() == {"detail": "gpx_invalid"}
    assert parse(b"<gpx></gpx>").json() == {"detail": "gpx_no_points"}
    tiny = (
        b'<gpx><trk><trkseg><trkpt lat="42" lon="1"/><trkpt lat="42" lon="1"/></trkseg></trk></gpx>'
    )
    assert parse(tiny).json() == {"detail": "route_too_short"}
    too_big = parse(b"<gpx>" + b" " * settings.max_gpx_bytes + b"</gpx>")
    assert too_big.status_code == 413
