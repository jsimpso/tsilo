"""Module model - represents a Terraform module identified by namespace, name, and provider."""

import re
import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from tsilo.models import Base, TimestampMixin, generate_uuid

MODULE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$")
PROVIDER_PATTERN = re.compile(r"^[a-z0-9-]+$")


class Module(Base, TimestampMixin):
    """Represents a Terraform module identified by namespace, name, and provider."""

    __tablename__ = "modules"
    __table_args__ = (UniqueConstraint("namespace_id", "name", "provider", name="uq_module_namespace_name_provider"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid)
    namespace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("namespaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    namespace: Mapped["Namespace"] = relationship(back_populates="modules")  # noqa: F821
    versions: Mapped[list["ModuleVersion"]] = relationship(  # noqa: F821
        back_populates="module", cascade="all, delete-orphan"
    )

    @validates("name")
    def validate_name(self, _key: str, value: str) -> str:
        if not MODULE_NAME_PATTERN.match(value):
            raise ValueError(
                "Module name must be lowercase alphanumeric with hyphens, "
                "2-100 characters, starting and ending with alphanumeric."
            )
        return value

    @validates("provider")
    def validate_provider(self, _key: str, value: str) -> str:
        if not PROVIDER_PATTERN.match(value):
            raise ValueError("Provider must be lowercase alphanumeric with hyphens.")
        return value

    def __repr__(self) -> str:
        return f"<Module(namespace_id={self.namespace_id}, name={self.name!r}, provider={self.provider!r})>"
