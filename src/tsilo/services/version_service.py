"""Module version service - version listing, retrieval, and semantic version comparison."""

import uuid
from functools import cmp_to_key

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from tsilo.models.module import Module
from tsilo.models.namespace import Namespace
from tsilo.models.version import ModuleVersion

logger = structlog.get_logger(__name__)


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
        """
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
