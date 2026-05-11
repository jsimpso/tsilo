"""DownloadMetric model - tracks usage data for module versions."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tsilo.models import Base, TimestampMixin, generate_uuid


class DownloadMetric(Base, TimestampMixin):
    """Tracks download counts and timestamps for module versions."""

    __tablename__ = "download_metrics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid)
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module_versions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    download_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_download_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    version: Mapped["ModuleVersion"] = relationship(back_populates="download_metric")  # noqa: F821

    def __repr__(self) -> str:
        return f"<DownloadMetric(version_id={self.version_id}, count={self.download_count})>"
