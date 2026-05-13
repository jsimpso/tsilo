"""Module version service - version listing, retrieval, creation, and semantic version comparison."""

import hashlib
import re
import uuid
from datetime import datetime, timezone
from functools import cmp_to_key

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from tsilo.models.metric import DownloadMetric
from tsilo.models.module import Module
from tsilo.models.namespace import Namespace
from tsilo.models.version import SEMVER_PATTERN, ModuleVersion
from tsilo.services.module_parser import ModuleParser, ParseError
from tsilo.services.storage_service import StorageService
from tsilo.services.cache import module_cache

logger = structlog.get_logger(__name__)

# Maximum upload size: 100 MB
MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024


def _semver_compare(a: str, b: str) -> int:
    """Compare two semantic versions. Returns negative if a < b, positive if a > b, 0 if equal."""

    def parse_version(v: str) -> tuple[int, int, int, str]:
        # Strip any pre-release/build metadata for main comparison
        parts = v.split("-", 1)
        main = parts[0]
        pre = parts[1] if len(parts) > 1 else ""
        segments = main.split(".")
        major = int(segments[0]) if len(segments) > 0 else 0
        minor = int(segments[1]) if len(segments) > 1 else 0
        patch = int(segments[2].split("+")[0]) if len(segments) > 2 else 0
        return (major, minor, patch, pre)

    a_parsed = parse_version(a)
    b_parsed = parse_version(b)

    # Compare major.minor.patch
    for i in range(3):
        if a_parsed[i] != b_parsed[i]:
            return a_parsed[i] - b_parsed[i]

    # Pre-release versions have lower precedence than release
    a_pre = a_parsed[3]
    b_pre = b_parsed[3]
    if a_pre and not b_pre:
        return -1
    if not a_pre and b_pre:
        return 1
    if a_pre < b_pre:
        return -1
    if a_pre > b_pre:
        return 1

    return 0


class VersionService:
    """Service for module version operations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_versions(self, namespace: str, name: str, provider: str) -> list[str] | None:
        """List all versions for a module in descending semantic version order.

        Returns None if the module does not exist.
        Returns an empty list if the module exists but has no versions.
        Results are cached for 5 minutes.
        """
        cache_key = f"versions:{namespace}/{name}/{provider}"
        cached = module_cache.get(cache_key)
        if cached is not None:
            return cached

        # Find the module
        stmt = (
            select(Module)
            .join(Namespace, Module.namespace_id == Namespace.id)
            .where(
                Namespace.name == namespace,
                Module.name == name,
                Module.provider == provider,
            )
        )
        result = await self._db.execute(stmt)
        module = result.scalar_one_or_none()

        if module is None:
            logger.info(
                "module_not_found",
                namespace=namespace,
                name=name,
                provider=provider,
            )
            return None

        # Get all versions
        versions_stmt = select(ModuleVersion.version).where(ModuleVersion.module_id == module.id)
        versions_result = await self._db.execute(versions_stmt)
        versions = list(versions_result.scalars().all())

        # Sort in descending semantic version order
        versions.sort(key=cmp_to_key(_semver_compare), reverse=True)

        # Cache the result
        module_cache.set(cache_key, versions)

        logger.info(
            "versions_listed",
            namespace=namespace,
            name=name,
            provider=provider,
            count=len(versions),
        )
        return versions

    async def get_version(self, namespace: str, name: str, provider: str, version: str) -> dict | None:
        """Get a specific module version.

        Returns None if the module or version does not exist.
        Returns a dict with version details if found.
        """
        stmt = (
            select(ModuleVersion)
            .join(Module, ModuleVersion.module_id == Module.id)
            .join(Namespace, Module.namespace_id == Namespace.id)
            .where(
                Namespace.name == namespace,
                Module.name == name,
                Module.provider == provider,
                ModuleVersion.version == version,
            )
            .options(joinedload(ModuleVersion.module))
        )
        result = await self._db.execute(stmt)
        module_version = result.scalar_one_or_none()

        if module_version is None:
            logger.info(
                "version_not_found",
                namespace=namespace,
                name=name,
                provider=provider,
                version=version,
            )
            return None

        return {
            "version_id": module_version.id,
            "module_id": module_version.module_id,
            "version": module_version.version,
            "package_url": module_version.package_url,
            "checksum_sha256": module_version.checksum_sha256,
            "published_at": module_version.published_at,
        }

    @staticmethod
    def validate_semver(version: str) -> bool:
        """Check if a version string is a valid semantic version."""
        return SEMVER_PATTERN.match(version) is not None

    async def check_version_exists(self, namespace: str, name: str, provider: str, version: str) -> bool:
        """Check if a specific module version already exists."""
        stmt = (
            select(ModuleVersion.id)
            .join(Module, ModuleVersion.module_id == Module.id)
            .join(Namespace, Module.namespace_id == Namespace.id)
            .where(
                Namespace.name == namespace,
                Module.name == name,
                Module.provider == provider,
                ModuleVersion.version == version,
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create_version(
        self,
        namespace: str,
        name: str,
        provider: str,
        version: str,
        file_data: bytes,
        user_id: uuid.UUID,
    ) -> dict:
        """Create a new module version from an uploaded package.

        Handles: parsing, checksum, S3 upload, DB record + DownloadMetric.
        Returns dict with created version details.
        Raises ValueError for validation errors, ParseError for bad packages.
        """
        # Validate semver
        if not self.validate_semver(version):
            raise ValueError(
                f"Invalid semantic version format: '{version}'. " "Expected format: MAJOR.MINOR.PATCH (e.g., 1.0.0)"
            )

        # Check file size
        if len(file_data) > MAX_UPLOAD_SIZE_BYTES:
            raise OverflowError(
                f"Module package size {len(file_data)} bytes exceeds limit "
                f"of {MAX_UPLOAD_SIZE_BYTES} bytes (100 MB)"
            )

        # Parse module package (validates tar.gz, extracts inputs/outputs/readme)
        parser = ModuleParser()
        metadata = parser.parse(file_data)

        # Calculate SHA256 checksum
        checksum = hashlib.sha256(file_data).hexdigest()

        # Find or create module record
        module = await self._get_or_create_module(namespace, name, provider)

        # Upload to S3
        storage = StorageService()
        package_url = storage.upload_module(namespace, name, provider, version, file_data, checksum)

        # Create ModuleVersion record
        now = datetime.now(tz=timezone.utc)
        module_version = ModuleVersion(
            module_id=module.id,
            version=version,
            inputs=metadata["inputs"],
            outputs=metadata["outputs"],
            readme=metadata.get("readme"),
            package_url=package_url,
            package_size_bytes=len(file_data),
            checksum_sha256=checksum,
            published_by=user_id,
            published_at=now,
        )
        self._db.add(module_version)

        # Create DownloadMetric record initialized to 0
        download_metric = DownloadMetric(
            version_id=module_version.id,
            download_count=0,
            last_download_at=None,
        )
        self._db.add(download_metric)

        await self._db.flush()

        # Invalidate cached version list for this module
        module_cache.invalidate(f"versions:{namespace}/{name}/{provider}")

        logger.info(
            "version_created",
            namespace=namespace,
            name=name,
            provider=provider,
            version=version,
            package_size_bytes=len(file_data),
            checksum_sha256=checksum,
            user_id=str(user_id),
        )

        return {
            "id": module_version.id,
            "module_id": module.id,
            "namespace": namespace,
            "name": name,
            "provider": provider,
            "version": version,
            "inputs": metadata["inputs"],
            "outputs": metadata["outputs"],
            "package_url": package_url,
            "package_size_bytes": len(file_data),
            "checksum_sha256": checksum,
            "published_at": now.isoformat(),
        }

    async def _get_or_create_module(self, namespace: str, name: str, provider: str) -> Module:
        """Get an existing module or create a new one."""
        # Find namespace
        ns_stmt = select(Namespace).where(Namespace.name == namespace)
        ns_result = await self._db.execute(ns_stmt)
        ns = ns_result.scalar_one_or_none()

        if ns is None:
            raise ValueError(f"Namespace '{namespace}' not found")

        # Find or create module
        mod_stmt = select(Module).where(
            Module.namespace_id == ns.id,
            Module.name == name,
            Module.provider == provider,
        )
        mod_result = await self._db.execute(mod_stmt)
        module = mod_result.scalar_one_or_none()

        if module is None:
            module = Module(
                namespace_id=ns.id,
                name=name,
                provider=provider,
            )
            self._db.add(module)
            await self._db.flush()
            logger.info(
                "module_created",
                namespace=namespace,
                name=name,
                provider=provider,
            )

        return module
