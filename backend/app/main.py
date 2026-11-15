"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .api import routes, sessions, view
from .config import Settings, get_settings
from .db import Base
from .services.cleanup import cleanup_loop
from .services.hub import Hub
from .services.ratelimit import RateLimiter


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_async_engine(settings.database_url)
        app.state.engine = engine
        app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        if settings.auto_create_tables:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        cleanup = asyncio.create_task(
            cleanup_loop(app.state.sessionmaker, app.state.hub, settings.cleanup_interval_seconds)
        )
        try:
            yield
        finally:
            cleanup.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cleanup
            await engine.dispose()

    app = FastAPI(
        title="donde-estoy API",
        summary="Live location sharing with a mountain-aware ETA.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.hub = Hub()
    app.state.create_limiter = RateLimiter(settings.create_rate_limit_per_hour, 3600)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(routes.router)
    app.include_router(sessions.router)
    app.include_router(view.router)

    @app.get("/api/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
