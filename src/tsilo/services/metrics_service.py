"""Metrics service - download count tracking, system metrics, deprecation detection."""

import uuid
from datetime import datetime, timedelta, timezone
from functools import cmp_to_key

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from tsilo.models.metric import DownloadMetric
from tsilo.models.module import Module
from tsilo.models.namespace import Namespace
from tsilo.models.user import User
from tsilo.models.version import ModuleVersion

logger = structlog.get_logger(__name__)

DEPRECATION_THRESHOLD_DAYS = 90


class MetricsService:
    """Service for tracking module download metrics."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def increment_download_count(self, version_id: uuid.UUID) -> None:
        """Increment download counter for a module version (async, non-blocking).

        Updates download_count and last_download_at timestamp.
        """
        now = datetime.now(tz=timezone.utc)
        stmt = (
            update(DownloadMetric)
            .where(DownloadMetric.version_id == version_id)
            .values(
                download_count=DownloadMetric.download_count + 1,
                last_download_at=now,
            )
        )
        await self._db.execute(stmt)

        logger.info(
            "download_count_incremented",
            version_id=str(version_id),
            timestamp=now.isoformat(),
        )

    async def get_system_metrics(self) -> dict:
        """Get system-wide metrics for admin overview dashboard."""
        now = datetime.now(tz=timezone.utc)
        thirty_days_ago = now - timedelta(days=30)

        # Total modules
        total_modules = (await self._db.execute(select(func.count()).select_from(Module))).scalar() or 0

        # Total versions
        total_versions = (await self._db.execute(select(func.count()).select_from(ModuleVersion))).scalar() or 0

        # Total namespaces
        total_namespaces = (await self._db.execute(select(func.count()).select_from(Namespace))).scalar() or 0

        # Total downloads
        total_downloads = (
            await self._db.execute(select(func.coalesce(func.sum(DownloadMetric.download_count), 0)))
        ).scalar() or 0

        # Downloads in last 30 days (approximation: versions with last_download_at in range)
        downloads_last_30 = (
            await self._db.execute(
                select(func.coalesce(func.sum(DownloadMetric.download_count), 0)).where(
                    DownloadMetric.last_download_at >= thirty_days_ago
                )
            )
        ).scalar() or 0

        # Active users last 30 days
        active_users = (
            await self._db.execute(select(func.count()).select_from(User).where(User.last_login_at >= thirty_days_ago))
        ).scalar() or 0

        # Top modules by total downloads
        top_modules_stmt = (
            select(
                Namespace.name.label("namespace"),
                Module.name.label("module_name"),
                Module.provider,
                func.coalesce(func.sum(DownloadMetric.download_count), 0).label("downloads"),
            )
            .join(ModuleVersion, ModuleVersion.module_id == Module.id)
            .join(DownloadMetric, DownloadMetric.version_id == ModuleVersion.id)
            .join(Namespace, Module.namespace_id == Namespace.id)
            .group_by(Namespace.name, Module.name, Module.provider)
            .order_by(func.sum(DownloadMetric.download_count).desc())
            .limit(10)
        )
        top_result = await self._db.execute(top_modules_stmt)
        top_modules = [
            {
                "namespace": row.namespace,
                "name": row.module_name,
                "provider": row.provider,
                "downloads": row.downloads,
            }
            for row in top_result
        ]

        # Namespace usage
        ns_usage_stmt = (
            select(
                Namespace.name.label("namespace"),
                func.count(func.distinct(Module.id)).label("module_count"),
                func.count(func.distinct(ModuleVersion.id)).label("version_count"),
                func.coalesce(func.sum(DownloadMetric.download_count), 0).label("total_downloads"),
            )
            .outerjoin(Module, Module.namespace_id == Namespace.id)
            .outerjoin(ModuleVersion, ModuleVersion.module_id == Module.id)
            .outerjoin(DownloadMetric, DownloadMetric.version_id == ModuleVersion.id)
            .group_by(Namespace.name)
            .order_by(func.coalesce(func.sum(DownloadMetric.download_count), 0).desc())
        )
        ns_result = await self._db.execute(ns_usage_stmt)
        namespace_usage = [
            {
                "namespace": row.namespace,
                "module_count": row.module_count,
                "version_count": row.version_count,
                "total_downloads": row.total_downloads,
            }
            for row in ns_result
        ]

        return {
            "total_modules": total_modules,
            "total_versions": total_versions,
            "total_namespaces": total_namespaces,
            "total_downloads": total_downloads,
            "downloads_last_30_days": downloads_last_30,
            "active_users_last_30_days": active_users,
            "top_modules": top_modules,
            "namespace_usage": namespace_usage,
        }

    async def get_module_metrics(self, namespace: str, name: str, provider: str) -> dict | None:
        """Get detailed metrics for a specific module.

        Returns None if the module is not found.
        """
        from tsilo.services.version_service import _semver_compare

        # Find the module
        stmt = (
            select(Module)
            .join(Namespace, Module.namespace_id == Namespace.id)
            .where(
                Namespace.name == namespace,
                Module.name == name,
                Module.provider == provider,
            )
            .options(
                joinedload(Module.versions).joinedload(ModuleVersion.download_metric),
            )
        )
        result = await self._db.execute(stmt)
        module = result.unique().scalar_one_or_none()

        if module is None:
            return None

        total_downloads = 0
        downloads_by_version = []

        for v in module.versions:
            dl_count = 0
            last_dl = None
            deprecated = False

            if v.download_metric:
                dl_count = v.download_metric.download_count
                last_dl = v.download_metric.last_download_at

            total_downloads += dl_count
            deprecated = self._is_deprecated(last_dl)

            downloads_by_version.append(
                {
                    "version": v.version,
                    "download_count": dl_count,
                    "last_download_at": last_dl,
                    "deprecated": deprecated,
                }
            )

        # Sort versions descending by semver
        downloads_by_version.sort(
            key=cmp_to_key(lambda a, b: _semver_compare(a["version"], b["version"])),
            reverse=True,
        )

        # Build downloads_over_time from last_download_at data (last 30 days)
        downloads_over_time = await self._get_downloads_over_time(module.id)

        return {
            "total_downloads": total_downloads,
            "downloads_by_version": downloads_by_version,
            "downloads_over_time": downloads_over_time,
        }

    async def _get_downloads_over_time(self, module_id: uuid.UUID) -> list[dict]:
        """Get daily download approximation for the last 30 days.

        Since we only track aggregate counts, this returns a simplified
        view based on last_download_at timestamps.
        """
        now = datetime.now(tz=timezone.utc)
        thirty_days_ago = now - timedelta(days=30)

        # Get versions with recent downloads
        stmt = (
            select(
                DownloadMetric.download_count,
                DownloadMetric.last_download_at,
            )
            .join(ModuleVersion, DownloadMetric.version_id == ModuleVersion.id)
            .where(
                ModuleVersion.module_id == module_id,
                DownloadMetric.last_download_at >= thirty_days_ago,
            )
        )
        result = await self._db.execute(stmt)
        rows = result.all()

        # Build date-based summary
        date_counts: dict[str, int] = {}
        for row in rows:
            if row.last_download_at:
                date_str = row.last_download_at.strftime("%Y-%m-%d")
                date_counts[date_str] = date_counts.get(date_str, 0) + row.download_count

        # Sort by date descending
        return [{"date": date, "count": count} for date, count in sorted(date_counts.items(), reverse=True)]

    def _is_deprecated(self, last_download_at: datetime | None) -> bool:
        """Check if a version should be flagged as deprecated.

        Versions with no downloads in 90+ days are considered deprecated.
        """
        if last_download_at is None:
            return False
        now = datetime.now(tz=timezone.utc)
        return (now - last_download_at).days > DEPRECATION_THRESHOLD_DAYS

    async def flag_deprecated_versions(self) -> list[dict]:
        """Identify module versions that should be flagged as deprecated.

        Returns a list of deprecated version info dicts.
        """
        threshold = datetime.now(tz=timezone.utc) - timedelta(days=DEPRECATION_THRESHOLD_DAYS)

        stmt = (
            select(
                ModuleVersion.id,
                ModuleVersion.version,
                Module.name.label("module_name"),
                Namespace.name.label("namespace"),
                Module.provider,
                DownloadMetric.last_download_at,
            )
            .join(DownloadMetric, DownloadMetric.version_id == ModuleVersion.id)
            .join(Module, ModuleVersion.module_id == Module.id)
            .join(Namespace, Module.namespace_id == Namespace.id)
            .where(DownloadMetric.last_download_at < threshold)
        )

        result = await self._db.execute(stmt)
        deprecated = []
        for row in result:
            deprecated.append(
                {
                    "version_id": str(row.id),
                    "version": row.version,
                    "module": row.module_name,
                    "namespace": row.namespace,
                    "provider": row.provider,
                    "last_download_at": row.last_download_at.isoformat() if row.last_download_at else None,
                }
            )

        logger.info(
            "deprecated_versions_flagged",
            count=len(deprecated),
        )

        return deprecated
