"""Health check, Prometheus metrics, admin metrics, and maintenance endpoints."""

import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.config import get_settings
from tsilo.middleware.auth import CurrentUser, get_current_user
from tsilo.models import get_db, get_session_factory
from tsilo.schemas.metrics import (
    MetricsOverviewResponse,
    ModuleMetricsResponse,
)
from tsilo.services.metrics_service import MetricsService
from tsilo.services.permission_service import PermissionService
from tsilo.services.storage_service import StorageService

logger = structlog.get_logger(__name__)

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
        factory = get_session_factory()
        async with factory() as session:
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


@router.post("/admin/cleanup-oauth-codes")
async def cleanup_oauth_codes(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete expired and used OAuth authorization codes.

    Removes codes expired >24h ago and used codes older than 7 days.
    Intended to be called hourly by a cron job or scheduler.
    """
    from tsilo.services.oauth_service import OAuthService

    oauth_service = OAuthService(db)
    deleted = await oauth_service.cleanup_expired_codes()
    return {"deleted_count": deleted}


@router.post("/admin/calculate-metrics")
async def calculate_metrics(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Aggregate download counts and identify deprecated versions.

    Intended to be called hourly by a cron job or scheduler.
    Returns summary of deprecated versions found.
    """
    metrics_service = MetricsService(db)
    deprecated = await metrics_service.flag_deprecated_versions()

    logger.info(
        "metrics_calculation_completed",
        deprecated_count=len(deprecated),
    )

    return {
        "deprecated_versions": len(deprecated),
        "details": deprecated,
    }


def _is_admin(user: CurrentUser) -> bool:
    """Check if the current user is an admin."""
    settings = get_settings()
    return settings.admin_group in (user.groups or [])


@router.get("/api/metrics/overview", response_model=MetricsOverviewResponse)
async def metrics_overview(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MetricsOverviewResponse:
    """Get system-wide metrics (admin only).

    Returns total modules, versions, namespaces, downloads,
    top modules, and namespace usage breakdown.
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for system metrics overview",
        )

    metrics_service = MetricsService(db)
    data = await metrics_service.get_system_metrics()

    logger.info(
        "metrics_overview_viewed",
        user_id=str(current_user.id),
    )

    return MetricsOverviewResponse(metrics=data)


@router.get(
    "/api/metrics/modules/{namespace}/{name}/{provider}",
    response_model=ModuleMetricsResponse,
)
async def module_metrics(
    namespace: str,
    name: str,
    provider: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ModuleMetricsResponse:
    """Get detailed metrics for a specific module.

    User must have read access to the module's namespace.
    """
    perm_service = PermissionService(db)
    if not await perm_service.check_read_access(current_user, namespace):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have read access to namespace '{namespace}'",
        )

    metrics_service = MetricsService(db)
    data = await metrics_service.get_module_metrics(namespace, name, provider)

    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module '{namespace}/{name}/{provider}' not found",
        )

    logger.info(
        "module_metrics_viewed",
        user_id=str(current_user.id),
        namespace=namespace,
        module=name,
        provider=provider,
    )

    return ModuleMetricsResponse(
        module={"namespace": namespace, "name": name, "provider": provider},
        metrics=data,
    )
