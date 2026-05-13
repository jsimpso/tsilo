"""ModuleVersion model - specific version of a module with metadata and package location."""

import re
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from tsilo.models import Base, generate_uuid

SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


class ModuleVersion(Base):
    """Represents a specific version of a module with metadata and package location."""

    __tablename__ = "module_versions"
    __table_args__ = (UniqueConstraint("module_id", "version", name="uq_module_version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid)
    module_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    inputs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    outputs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    readme: Mapped[str | None] = mapped_column(Text, nullable=True)
    package_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    package_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    published_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")

    # Relationships
    module: Mapped["Module"] = relationship(back_populates="versions")  # noqa: F821
    publisher: Mapped["User | None"] = relationship()  # noqa: F821
    download_metric: Mapped["DownloadMetric | None"] = relationship(  # noqa: F821
        back_populates="version", uselist=False, cascade="all, delete-orphan"
    )

    @validates("version")
    def validate_version(self, _key: str, value: str) -> str:
        if not SEMVER_PATTERN.match(value):
            raise ValueError(f"Version '{value}' is not a valid semantic version.")
        return value

    @validates("checksum_sha256")
    def validate_checksum(self, _key: str, value: str) -> str:
        if len(value) != 64 or not all(c in "0123456789abcdef" for c in value.lower()):
            raise ValueError("checksum_sha256 must be a 64-character hex string.")
        return value.lower()

    def __repr__(self) -> str:
        return f"<ModuleVersion(module_id={self.module_id}, version={self.version!r})>"
