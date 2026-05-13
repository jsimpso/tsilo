"""Pydantic schemas for namespace API - create, list, and permission responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NamespaceCreate(BaseModel):
    """Request body for POST /api/namespaces."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
        description="Namespace identifier (lowercase alphanumeric with hyphens)",
    )
    display_name: str | None = Field(
        None,
        max_length=200,
        description="Human-readable display name",
    )
    description: str | None = Field(
        None,
        description="Namespace description",
    )


class NamespaceResponse(BaseModel):
    """Single namespace entry in responses."""

    id: uuid.UUID
    name: str
    display_name: str | None = None
    description: str | None = None
    module_count: int = 0
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime


class NamespaceListResponse(BaseModel):
    """Response for GET /api/namespaces."""

    namespaces: list[NamespaceResponse]


class PermissionCreate(BaseModel):
    """Request body for creating a namespace permission."""

    group_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="OIDC group name to grant access to",
    )
    permission_level: str = Field(
        ...,
        pattern=r"^(read|write)$",
        description="Permission level: 'read' or 'write'",
    )


class PermissionResponse(BaseModel):
    """Single permission entry in responses."""

    id: uuid.UUID
    group_name: str
    permission_level: str
    created_at: datetime


class PermissionListResponse(BaseModel):
    """Response for GET /api/namespaces/:namespace/permissions."""

    permissions: list[PermissionResponse]
