"""Metrics service - download count tracking."""

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.models.metric import DownloadMetric

logger = structlog.get_logger(__name__)


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
