"""Stateless GPX parsing, so the runner can preview a route before starting."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile

from app.deps import AppSettings
from app.schemas import MAX_ROUTE_POINTS, ParsedRoute
from app.services.gpx import GpxError, parse_gpx
from app.services.route import RouteError, build_route
from app.services.snapshot import route_out

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.post("/parse", response_model=ParsedRoute)
async def parse_route(file: UploadFile, settings: AppSettings) -> ParsedRoute:
    """Parse an uploaded GPX file. Nothing is stored."""
    content = await file.read(settings.max_gpx_bytes + 1)
    if len(content) > settings.max_gpx_bytes:
        raise HTTPException(413, "gpx_too_large")
    try:
        name, points = parse_gpx(content)
        if len(points) > MAX_ROUTE_POINTS:
            # Thin out huge recordings evenly, always keeping the last point.
            stride = len(points) // MAX_ROUTE_POINTS + 1
            points = points[:-1:stride] + [points[-1]]
        route = build_route(points)
    except GpxError as exc:
        raise HTTPException(422, exc.code) from exc
    except RouteError as exc:
        raise HTTPException(422, "route_too_short") from exc
    return ParsedRoute(name=name, raw_points=points, **route_out(route).model_dump())
