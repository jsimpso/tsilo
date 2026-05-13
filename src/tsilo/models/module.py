"""Module model - represents a Terraform module identified by namespace, name, and system."""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from tsilo.models import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from tsilo.models.namespace import Namespace
    from tsilo.models.version import ModuleVersion

MODULE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$")
SYSTEM_PATTERN = re.compile(r"^[a-z0-9-]+$")


class Module(Base, TimestampMixin):
    """Represents a Terraform module identified by namespace, name, and target system.

    The "system" segment corresponds to the third path component of a Terraform
    module address per the Terraform Module Registry Protocol (see
    docs/module_registry_protocol.md). It is the name of the remote system the
    module is primarily written to target, and commonly matches a provider name
    such as "aws" or "azurerm".
    """

    __tablename__ = "modules"
    __table_args__ = (
        UniqueConstraint("namespace_id", "name", "system", name="uq_module_namespace_name_system"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid)
    namespace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("namespaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    system: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    namespace: Mapped[Namespace] = relationship(back_populates="modules")
    versions: Mapped[list[ModuleVersion]] = relationship(
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

    @validates("system")
    def validate_system(self, _key: str, value: str) -> str:
        if not SYSTEM_PATTERN.match(value):
            raise ValueError("System must be lowercase alphanumeric with hyphens.")
        return value

    def __repr__(self) -> str:
        return (
            f"<Module(namespace_id={self.namespace_id},"
            f" name={self.name!r}, system={self.system!r})>"
        )
