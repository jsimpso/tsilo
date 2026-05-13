"""DownloadMetric model - tracks usage data for module versions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tsilo.models import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from tsilo.models.version import ModuleVersion


class DownloadMetric(Base, TimestampMixin):
    """Tracks download counts and timestamps for module versions."""

    __tablename__ = "download_metrics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid)
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module_versions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    download_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_download_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Relationships
    version: Mapped[ModuleVersion] = relationship(back_populates="download_metric")

    def __repr__(self) -> str:
        return f"<DownloadMetric(version_id={self.version_id}, count={self.download_count})>"
