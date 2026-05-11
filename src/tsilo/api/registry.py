"""Terraform Module Registry Protocol endpoints."""

import structlog
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.middleware.auth import CurrentUser, get_current_user
from tsilo.models import get_db
from tsilo.schemas.terraform import (
    ServiceDiscoveryResponse,
)
from tsilo.services.permission_service import PermissionService
from tsilo.services.storage_service import StorageService

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
