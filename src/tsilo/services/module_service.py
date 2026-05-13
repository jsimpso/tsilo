"""Module service - listing, searching, and retrieving modules with permissions."""

import math
import uuid
from functools import cmp_to_key

import structlog
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from tsilo.middleware.auth import CurrentUser
from tsilo.models.metric import DownloadMetric
from tsilo.models.module import Module
from tsilo.models.namespace import Namespace
from tsilo.models.permission import NamespacePermission, PermissionLevel
from tsilo.models.version import ModuleVersion
from tsilo.services.version_service import _semver_compare

logger = structlog.get_logger(__name__)


class ModuleService:
    """Service for module listing, search, and detail operations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def _authorized_namespaces_filter(self, user: CurrentUser, query: Select) -> Select:
        """Filter query to only include modules from namespaces the user can read."""
        if not user.groups:
            return query.where(False)  # No groups => no access

        subq = (
            select(Namespace.id)
            .join(NamespacePermission, NamespacePermission.namespace_id == Namespace.id)
            .where(
                NamespacePermission.group_name.in_(user.groups),
                NamespacePermission.permission_level.in_(
                    [PermissionLevel.READ, PermissionLevel.WRITE]
                ),
            )
            .distinct()
            .scalar_subquery()
        )
        return query.where(Module.namespace_id.in_(subq))

    async def list_modules(
        self,
        user: CurrentUser,
        namespace: str | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict:
        """List modules with optional filtering and pagination.

        Only returns modules from namespaces the user has read access to.
        """
        per_page = min(per_page, 100)
        page = max(page, 1)

        # Base query
        base_query = select(Module).join(Namespace, Module.namespace_id == Namespace.id)
        base_query = self._authorized_namespaces_filter(user, base_query)

        # Apply filters
        if namespace:
            base_query = base_query.where(Namespace.name == namespace)
        if search:
            search_term = f"%{search}%"
            base_query = base_query.where(
                Module.name.ilike(search_term) | Module.description.ilike(search_term)
            )

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self._db.execute(count_query)
        total_count = total_result.scalar() or 0

        total_pages = max(1, math.ceil(total_count / per_page))

        # Fetch page
        offset = (page - 1) * per_page
        modules_query = (
            base_query.options(joinedload(Module.namespace), joinedload(Module.versions))
            .order_by(Module.updated_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        result = await self._db.execute(modules_query)
        modules = result.unique().scalars().all()

        items = []
        for mod in modules:
            # Calculate aggregates
            versions = mod.versions or []
            version_count = len(versions)

            # Get latest version by semver
            latest_version = None
            last_updated = mod.updated_at
            if versions:
                sorted_versions = sorted(
                    versions,
                    key=cmp_to_key(lambda a, b: _semver_compare(a.version, b.version)),
                    reverse=True,
                )
                latest_version = sorted_versions[0].version
                last_updated = sorted_versions[0].published_at

            # Get total downloads
            version_ids = [v.id for v in versions]
            total_downloads = 0
            if version_ids:
                dl_query = select(func.coalesce(func.sum(DownloadMetric.download_count), 0)).where(
                    DownloadMetric.version_id.in_(version_ids)
                )
                dl_result = await self._db.execute(dl_query)
                total_downloads = dl_result.scalar() or 0

            items.append(
                {
                    "id": mod.id,
                    "namespace": mod.namespace.name,
                    "name": mod.name,
                    "provider": mod.provider,
                    "description": mod.description,
                    "latest_version": latest_version,
                    "version_count": version_count,
                    "total_downloads": total_downloads,
                    "last_updated": last_updated,
                }
            )

        return {
            "modules": items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "total_count": total_count,
            },
        }

    async def get_module_with_versions(
        self, namespace: str, name: str, provider: str
    ) -> dict | None:
        """Get detailed module info with all versions.

        Returns None if module not found.
        """
        stmt = (
            select(Module)
            .join(Namespace, Module.namespace_id == Namespace.id)
            .where(
                Namespace.name == namespace,
                Module.name == name,
                Module.provider == provider,
            )
            .options(
                joinedload(Module.namespace),
                joinedload(Module.versions).joinedload(ModuleVersion.download_metric),
            )
        )
        result = await self._db.execute(stmt)
        module = result.unique().scalar_one_or_none()

        if module is None:
            return None

        # Build version summaries
        versions_data = []
        total_downloads = 0
        for v in module.versions:
            dl_count = 0
            last_dl = None
            if v.download_metric:
                dl_count = v.download_metric.download_count
                last_dl = v.download_metric.last_download_at
            total_downloads += dl_count

            deprecated = False
            deprecation_reason = None
            if last_dl:
                from datetime import datetime, timezone

                days_since = (datetime.now(tz=timezone.utc) - last_dl).days
                if days_since > 90:
                    deprecated = True
                    deprecation_reason = "No downloads in 90+ days"

            versions_data.append(
                {
                    "version": v.version,
                    "published_at": v.published_at,
                    "download_count": dl_count,
                    "last_download_at": last_dl,
                    "deprecated": deprecated,
                    "deprecation_reason": deprecation_reason,
                }
            )

        # Sort versions descending
        versions_data.sort(
            key=cmp_to_key(lambda a, b: _semver_compare(a["version"], b["version"])),
            reverse=True,
        )

        latest_version = versions_data[0]["version"] if versions_data else None

        return {
            "id": module.id,
            "namespace": module.namespace.name,
            "name": module.name,
            "provider": module.provider,
            "description": module.description,
            "source_url": module.source_url,
            "created_at": module.created_at,
            "versions": versions_data,
            "latest_version": latest_version,
            "total_downloads": total_downloads,
        }

    async def get_version_detail(
        self, namespace: str, name: str, provider: str, version: str
    ) -> dict | None:
        """Get detailed version info including inputs, outputs, and README.

        Returns None if not found.
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
            .options(
                joinedload(ModuleVersion.module).joinedload(Module.namespace),
                joinedload(ModuleVersion.publisher),
                joinedload(ModuleVersion.download_metric),
            )
        )
        result = await self._db.execute(stmt)
        mv = result.unique().scalar_one_or_none()

        if mv is None:
            return None

        publisher_info = None
        if mv.publisher:
            publisher_info = {
                "id": mv.publisher.id,
                "name": mv.publisher.name,
                "email": mv.publisher.email,
            }

        dl_count = 0
        last_dl = None
        if mv.download_metric:
            dl_count = mv.download_metric.download_count
            last_dl = mv.download_metric.last_download_at

        # Generate usage example
        ns_name = mv.module.namespace.name
        mod_name = mv.module.name
        prov = mv.module.provider
        from tsilo.config import get_settings

        registry_host = get_settings().app_base_url.replace("https://", "").replace("http://", "")
        usage_example = (
            f'module "{mod_name}" {{\n'
            f'  source  = "{registry_host}/{ns_name}/{mod_name}/{prov}"\n'
            f'  version = "{mv.version}"\n'
            f"}}"
        )

        return {
            "id": mv.id,
            "module_id": mv.module_id,
            "version": mv.version,
            "inputs": mv.inputs or [],
            "outputs": mv.outputs or [],
            "readme": mv.readme,
            "usage_example": usage_example,
            "package_size_bytes": mv.package_size_bytes,
            "checksum_sha256": mv.checksum_sha256,
            "published_by": publisher_info,
            "published_at": mv.published_at,
            "download_count": dl_count,
            "last_download_at": last_dl,
        }
