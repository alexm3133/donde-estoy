"""API test fixtures: a fresh app + SQLite file per test."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

from .helpers import north_of_start


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        auto_create_tables=True,
        public_url="https://donde.example",
        create_rate_limit_per_hour=0,
        cleanup_interval_seconds=3600,  # tests trigger purges explicitly
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


class Runner:
    """Drives the runner side of the API in tests."""

    def __init__(self, client: TestClient, **create_overrides) -> None:
        self.client = client
        lat, lon = north_of_start(2000)
        body = {"runner_name": "Alex", "destination": {"lat": lat, "lon": lon}} | create_overrides
        if "route_points" in create_overrides:
            body.pop("destination")
        response = client.post("/api/sessions", json=body)
        assert response.status_code == 201, response.text
        self.created = response.json()
        self.id = self.created["id"]
        self.view_token = self.created["view_token"]
        self.headers = {"Authorization": f"Bearer {self.created['runner_token']}"}
        self.clock = datetime.now(UTC) - timedelta(minutes=30)

    def post(self, positions: list[dict], **extra):
        return self.client.post(
            f"/api/sessions/{self.id}/positions",
            json={"positions": positions, **extra},
            headers=self.headers,
        )

    def move_to(self, meters_north: float, after_s: float = 10.0, **fields) -> dict:
        """Report a fix ``meters_north`` of the origin, ``after_s`` later."""
        self.clock += timedelta(seconds=after_s)
        lat, lon = north_of_start(meters_north)
        response = self.post(
            [{"lat": lat, "lon": lon, "accuracy": 8, "ts": self.clock.isoformat(), **fields}]
        )
        assert response.status_code == 200, response.text
        return response.json()

    def view(self):
        return self.client.get(f"/api/view/{self.view_token}")


@pytest.fixture
def runner(client) -> Runner:
    return Runner(client)
