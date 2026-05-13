"""APIToken model - credentials for CI/CD pipeline authentication."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tsilo.models import Base, generate_uuid

if TYPE_CHECKING:
    from tsilo.models.user import User


class APIToken(Base):
    """Credentials for CI/CD pipeline authentication with scope limitations."""

    __tablename__ = "api_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scopes: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="api_tokens")

    @property
    def is_valid(self) -> bool:
        """Check if token is still valid (not expired and not revoked)."""

        now = datetime.now(tz=UTC)
        return self.expires_at > now and self.revoked_at is None

    def __repr__(self) -> str:
        return f"<APIToken(name={self.name!r}, user_id={self.user_id})>"
