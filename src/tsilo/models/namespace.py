"""Namespace model - logical container for modules."""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from tsilo.models import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from tsilo.models.module import Module
    from tsilo.models.permission import NamespacePermission

NAMESPACE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$")


class Namespace(Base, TimestampMixin):
    """Logical container for modules representing teams, projects, or organizational units."""

    __tablename__ = "namespaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(Unicode(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    modules: Mapped[list[Module]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )
    permissions: Mapped[list[NamespacePermission]] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )

    @validates("name")
    def validate_name(self, _key: str, value: str) -> str:
        if not NAMESPACE_NAME_PATTERN.match(value):
            raise ValueError(
                "Namespace name must be lowercase alphanumeric with hyphens, "
                "2-100 characters, starting and ending with alphanumeric."
            )
        if "--" in value:
            raise ValueError("Namespace name cannot contain consecutive hyphens.")
        return value

    def __repr__(self) -> str:
        return f"<Namespace(name={self.name!r})>"
