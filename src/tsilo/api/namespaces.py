"""Namespace management API endpoints."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.config import get_settings
from tsilo.middleware.auth import CurrentUser, get_current_user
from tsilo.models import get_db
from tsilo.schemas.namespace import (
    NamespaceCreate,
    NamespaceListResponse,
    NamespaceResponse,
    PermissionCreate,
    PermissionListResponse,
    PermissionResponse,
)
from tsilo.services.namespace_service import NamespaceService
from tsilo.services.permission_service import PermissionService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/namespaces", tags=["namespaces"])


def _is_admin(user: CurrentUser) -> bool:
    """Check if user belongs to the admin group."""
    settings = get_settings()
    return settings.admin_group in (user.groups or [])


@router.get("", response_model=NamespaceListResponse)
async def list_namespaces(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NamespaceListResponse:
    """List namespaces the current user has access to."""
    ns_service = NamespaceService(db)
    items = await ns_service.list_user_namespaces(current_user)

    logger.info(
        "namespaces_listed",
        user_id=str(current_user.id),
        count=len(items),
    )

    return NamespaceListResponse(namespaces=[NamespaceResponse(**ns) for ns in items])


@router.post("", response_model=NamespaceResponse, status_code=201)
async def create_namespace(
    body: NamespaceCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NamespaceResponse:
    """Create a new namespace (admin only)."""
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create namespaces",
        )

    ns_service = NamespaceService(db)
    try:
        result = await ns_service.create_namespace(
            name=body.name,
            display_name=body.display_name,
            description=body.description,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from None

    await db.commit()

    logger.info(
        "namespace_created",
        user_id=str(current_user.id),
        namespace=body.name,
    )

    return NamespaceResponse(**result)


@router.get(
    "/{namespace}/permissions",
    response_model=PermissionListResponse,
)
async def list_namespace_permissions(
    namespace: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PermissionListResponse:
    """List permissions for a namespace.

    User must have access to the namespace or be an admin.
    """
    perm_service = PermissionService(db)

    # Check access: admin or user with any access to namespace
    if not _is_admin(current_user) and not await perm_service.check_read_access(
        current_user, namespace
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have access to namespace '{namespace}'",
        )

    ns_service = NamespaceService(db)
    ns = await ns_service.get_namespace_by_name(namespace)
    if ns is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Namespace '{namespace}' not found",
        )

    permissions = await perm_service.list_namespace_permissions(namespace)

    logger.info(
        "namespace_permissions_listed",
        user_id=str(current_user.id),
        namespace=namespace,
        count=len(permissions),
    )

    return PermissionListResponse(permissions=[PermissionResponse(**p) for p in permissions])


@router.post(
    "/{namespace}/permissions",
    response_model=PermissionResponse,
    status_code=201,
)
async def create_permission(
    namespace: str,
    body: PermissionCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PermissionResponse:
    """Add a permission to a namespace (admin only)."""
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage permissions",
        )

    ns_service = NamespaceService(db)
    ns = await ns_service.get_namespace_by_name(namespace)
    if ns is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Namespace '{namespace}' not found",
        )

    perm_service = PermissionService(db)
    try:
        result = await perm_service.create_permission(
            namespace_name=namespace,
            group_name=body.group_name,
            permission_level=body.permission_level,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from None

    await db.commit()

    logger.info(
        "permission_created",
        user_id=str(current_user.id),
        namespace=namespace,
        group=body.group_name,
        level=body.permission_level,
    )

    return PermissionResponse(**result)


@router.delete(
    "/{namespace}/permissions/{permission_id}",
    status_code=204,
)
async def delete_permission(
    namespace: str,
    permission_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a permission from a namespace (admin only)."""
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage permissions",
        )

    ns_service = NamespaceService(db)
    ns = await ns_service.get_namespace_by_name(namespace)
    if ns is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Namespace '{namespace}' not found",
        )

    perm_service = PermissionService(db)
    deleted = await perm_service.delete_permission(permission_id, namespace)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission '{permission_id}' not found in namespace '{namespace}'",
        )

    await db.commit()

    logger.info(
        "permission_deleted",
        user_id=str(current_user.id),
        namespace=namespace,
        permission_id=str(permission_id),
    )
