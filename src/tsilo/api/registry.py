"""Terraform Module Registry Protocol endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.middleware.auth import CurrentUser, get_current_user
from tsilo.models import get_db
from tsilo.schemas.terraform import (
    ModuleVersionsEntry,
    ServiceDiscoveryResponse,
    VersionEntry,
    VersionsResponse,
)
from tsilo.services.metrics_service import MetricsService
from tsilo.services.permission_service import PermissionService
from tsilo.services.storage_service import StorageService
from tsilo.services.version_service import VersionService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["registry"])


@router.get("/.well-known/terraform.json")
async def service_discovery() -> Response:
    """Terraform remote service discovery endpoint (required by protocol).

    No authentication required. Response is cacheable for 1 hour.
    """
    data = ServiceDiscoveryResponse()
    return Response(
        content=data.model_dump_json(by_alias=True),
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/v1/modules/{namespace}/{name}/{provider}/versions")
async def list_versions(
    namespace: str,
    name: str,
    provider: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """List available versions for a module.

    Authentication required. Returns versions in descending semantic version order.
    """
    # Check permission
    perm_service = PermissionService(db)
    if not await perm_service.check_read_access(current_user, namespace):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have read access to namespace '{namespace}'",
        )

    # Get versions
    version_service = VersionService(db)
    versions = await version_service.list_versions(namespace, name, provider)

    if versions is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module '{namespace}/{name}/{provider}' not found",
        )

    response_data = VersionsResponse(
        modules=[ModuleVersionsEntry(versions=[VersionEntry(version=v) for v in versions])]
    )

    return Response(
        content=response_data.model_dump_json(),
        media_type="application/json",
        headers={"Cache-Control": "private, max-age=300"},
    )
