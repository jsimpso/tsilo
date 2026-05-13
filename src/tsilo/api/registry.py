"""Terraform Module Registry Protocol endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
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
from tsilo.services.module_parser import ParseError
from tsilo.services.permission_service import PermissionService
from tsilo.services.storage_service import StorageService
from tsilo.services.version_service import MAX_UPLOAD_SIZE_BYTES, VersionService

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
        logger.warning(
            "access_denied",
            user_id=str(current_user.id),
            namespace=namespace,
            module=name,
            provider=provider,
            action="list_versions",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have read access to namespace '{namespace}'",
        )

    # Get versions
    version_service = VersionService(db)
    versions = await version_service.list_versions(namespace, name, provider)

    if versions is None:
        logger.info(
            "module_not_found",
            namespace=namespace,
            module=name,
            provider=provider,
            action="list_versions",
        )
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


@router.get("/v1/modules/{namespace}/{name}/{provider}/{version}/download")
async def download_module(
    namespace: str,
    name: str,
    provider: str,
    version: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Provide download URL for a specific module version.

    Returns 204 with X-Terraform-Get header containing a pre-signed S3 URL.
    Authentication required. Download counter is incremented asynchronously.
    """
    # Check permission
    perm_service = PermissionService(db)
    if not await perm_service.check_read_access(current_user, namespace):
        logger.warning(
            "access_denied",
            user_id=str(current_user.id),
            namespace=namespace,
            module=name,
            provider=provider,
            version=version,
            action="download",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have read access to namespace '{namespace}'",
        )

    # Get version details
    version_service = VersionService(db)
    version_info = await version_service.get_version(namespace, name, provider, version)

    if version_info is None:
        logger.info(
            "version_not_found",
            namespace=namespace,
            module=name,
            provider=provider,
            version=version,
            action="download",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version '{version}' of module '{namespace}/{name}/{provider}' not found",
        )

    # Generate pre-signed download URL
    storage = StorageService()
    download_url = storage.generate_download_url(namespace, name, provider, version)

    # Increment download counter (non-blocking)
    metrics_service = MetricsService(db)
    await metrics_service.increment_download_count(version_info["version_id"])

    logger.info(
        "module_downloaded",
        user_id=str(current_user.id),
        user_email=current_user.email,
        namespace=namespace,
        module=name,
        provider=provider,
        version=version,
    )

    return Response(
        status_code=204,
        headers={
            "X-Terraform-Get": download_url,
            "Cache-Control": "no-store",
        },
    )


@router.post("/v1/modules/{namespace}/{name}/{provider}/{version}", status_code=201)
async def upload_module(
    namespace: str,
    name: str,
    provider: str,
    version: str,
    file: UploadFile,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Upload a new module version.

    Accepts a multipart .tar.gz file upload. Validates the version format,
    checks for duplicates, parses module metadata, uploads to S3, and creates
    database records.
    """
    # Check write permission
    perm_service = PermissionService(db)
    if not await perm_service.check_write_access(current_user, namespace):
        logger.warning(
            "access_denied",
            user_id=str(current_user.id),
            namespace=namespace,
            module=name,
            provider=provider,
            version=version,
            action="upload",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have write access to namespace '{namespace}'",
        )

    # Validate semantic version format
    if not VersionService.validate_semver(version):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid semantic version format: '{version}'. Expected format: MAJOR.MINOR.PATCH (e.g., 1.0.0)",
        )

    # Check for duplicate version
    version_service = VersionService(db)
    if await version_service.check_version_exists(namespace, name, provider, version):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version '{version}' of module '{namespace}/{name}/{provider}' already exists",
        )

    # Read file data
    file_data = await file.read()

    # Check file size
    if len(file_data) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"Module package size {len(file_data)} bytes exceeds limit "
                f"of {MAX_UPLOAD_SIZE_BYTES} bytes (100 MB)"
            ),
        )

    # Create version (parse, checksum, upload to S3, create DB records)
    try:
        result = await version_service.create_version(
            namespace=namespace,
            name=name,
            provider=provider,
            version=version,
            file_data=file_data,
            user_id=current_user.id,
        )
    except ParseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    logger.info(
        "module_uploaded",
        user_id=str(current_user.id),
        user_email=current_user.email,
        namespace=namespace,
        module=name,
        provider=provider,
        version=version,
        package_size_bytes=len(file_data),
    )

    return Response(
        content=_upload_response_json(result),
        status_code=201,
        media_type="application/json",
    )


def _upload_response_json(result: dict) -> str:
    """Serialize the upload result to JSON."""
    import json
    return json.dumps({
        "id": str(result["id"]),
        "namespace": result["namespace"],
        "name": result["name"],
        "provider": result["provider"],
        "version": result["version"],
        "inputs": result["inputs"],
        "outputs": result["outputs"],
        "package_url": result["package_url"],
        "package_size_bytes": result["package_size_bytes"],
        "checksum_sha256": result["checksum_sha256"],
        "published_at": result["published_at"],
    })
