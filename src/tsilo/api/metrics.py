"""Health check and Prometheus metrics endpoints."""

import time

from fastapi import APIRouter, Response
from sqlalchemy import text

from tsilo.models import async_session_factory
from tsilo.services.storage_service import StorageService

router = APIRouter(tags=["observability"])

# Simple in-memory metrics counters
_metrics = {
    "requests_total": 0,
    "requests_duration_seconds_sum": 0.0,
    "downloads_total": 0,
}


def increment_request_metrics(duration_seconds: float) -> None:
    """Increment request counter and duration sum."""
    _metrics["requests_total"] += 1
    _metrics["requests_duration_seconds_sum"] += duration_seconds


def increment_download_count() -> None:
    """Increment download counter."""
    _metrics["downloads_total"] += 1


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint with database and S3 connectivity checks.

    Returns:
        200 with status details if healthy
        503 if any dependency is unhealthy
    """
    checks: dict[str, str] = {}

    # Database connectivity
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {e}"

    # S3 connectivity
    try:
        storage = StorageService()
        if storage.check_connectivity():
            checks["storage"] = "healthy"
        else:
            checks["storage"] = "unhealthy: bucket not accessible"
    except Exception as e:
        checks["storage"] = f"unhealthy: {e}"

    overall = all(v == "healthy" for v in checks.values())

    response_data = {
        "status": "healthy" if overall else "unhealthy",
        "checks": checks,
        "timestamp": time.time(),
    }

    if not overall:
        return Response(
            content=str(response_data),
            status_code=503,
            media_type="application/json",
        )

    return response_data


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """Prometheus-compatible metrics endpoint.

    Returns metrics in Prometheus text exposition format.
    """
    lines = [
        "# HELP tsilo_requests_total Total number of HTTP requests.",
        "# TYPE tsilo_requests_total counter",
        f'tsilo_requests_total {_metrics["requests_total"]}',
        "",
        "# HELP tsilo_requests_duration_seconds_sum Total request duration in seconds.",
        "# TYPE tsilo_requests_duration_seconds_sum counter",
        f'tsilo_requests_duration_seconds_sum {_metrics["requests_duration_seconds_sum"]:.6f}',
        "",
        "# HELP tsilo_downloads_total Total number of module downloads.",
        "# TYPE tsilo_downloads_total counter",
        f'tsilo_downloads_total {_metrics["downloads_total"]}',
        "",
    ]

    return Response(
        content="\n".join(lines),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
