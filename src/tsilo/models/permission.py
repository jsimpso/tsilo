"""NamespacePermission model - maps groups to namespaces with permission levels."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from tsilo.models import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from tsilo.models.namespace import Namespace


class PermissionLevel(StrEnum):
    READ = "read"
    WRITE = "write"


class NamespacePermission(Base, TimestampMixin):
    """Maps OIDC groups to namespaces with permission levels (read, write)."""

    __tablename__ = "namespace_permissions"
    __table_args__ = (
        UniqueConstraint(
            "namespace_id",
            "group_name",
            "permission_level",
            name="uq_namespace_group_permission",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid)
    namespace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("namespaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    permission_level: Mapped[PermissionLevel] = mapped_column(String(10), nullable=False)

    # Relationships
    namespace: Mapped[Namespace] = relationship(back_populates="permissions")

    @validates("group_name")
    def validate_group_name(self, _key: str, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("group_name must not be empty.")
        return value.strip()

    def __repr__(self) -> str:
        return (
            f"<NamespacePermission(namespace_id={self.namespace_id}, "
            f"group={self.group_name!r}, level={self.permission_level})>"
        )
