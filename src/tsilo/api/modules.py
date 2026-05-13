"""Web UI module browsing API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.middleware.auth import CurrentUser, get_current_user
from tsilo.models import get_db
from tsilo.schemas.module import (
    ModuleDetailResponse,
    ModuleListResponse,
    VersionDetailResponse,
)
from tsilo.services.module_service import ModuleService
from tsilo.services.permission_service import PermissionService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/modules", tags=["modules"])


@router.get("", response_model=ModuleListResponse)
async def list_modules(
    namespace: str | None = Query(None, description="Filter by namespace"),
    search: str | None = Query(None, description="Search across name and description"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ModuleListResponse:
    """List modules with filtering and pagination.

    Only returns modules from namespaces the user has read access to.
    """
    module_service = ModuleService(db)
    result = await module_service.list_modules(
        user=current_user,
        namespace=namespace,
        search=search,
        page=page,
        per_page=per_page,
    )

    logger.info(
        "modules_listed",
        user_id=str(current_user.id),
        namespace=namespace,
        search=search,
        page=page,
        per_page=per_page,
        total_count=result["pagination"]["total_count"],
    )

    return ModuleListResponse(**result)


@router.get("/{namespace}/{name}/{system}", response_model=ModuleDetailResponse)
async def get_module_detail(
    namespace: str,
    name: str,
    system: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ModuleDetailResponse:
    """Get detailed module information with version list.

    User must have read access to the module's namespace.
    """
    perm_service = PermissionService(db)
    if not await perm_service.check_read_access(current_user, namespace):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have read access to namespace '{namespace}'",
        )

    module_service = ModuleService(db)
    result = await module_service.get_module_with_versions(namespace, name, system)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module '{namespace}/{name}/{system}' not found",
        )

    logger.info(
        "module_detail_viewed",
        user_id=str(current_user.id),
        namespace=namespace,
        module=name,
        system=system,
    )

    return ModuleDetailResponse(module=result)


@router.get(
    "/{namespace}/{name}/{system}/{version}",
    response_model=VersionDetailResponse,
)
async def get_version_detail(
    namespace: str,
    name: str,
    system: str,
    version: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VersionDetailResponse:
    """Get specific version details including inputs, outputs, and README.

    User must have read access to the module's namespace.
    """
    perm_service = PermissionService(db)
    if not await perm_service.check_read_access(current_user, namespace):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have read access to namespace '{namespace}'",
        )

    module_service = ModuleService(db)
    result = await module_service.get_version_detail(namespace, name, system, version)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version '{version}' of module '{namespace}/{name}/{system}' not found",
        )

    logger.info(
        "version_detail_viewed",
        user_id=str(current_user.id),
        namespace=namespace,
        module=name,
        system=system,
        version=version,
    )

    return VersionDetailResponse(version=result)
