"""User model - represents an authenticated user from OIDC provider."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, String, Unicode
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tsilo.models import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from tsilo.models.api_token import APIToken
    from tsilo.models.oauth_code import OAuthAuthorizationCode


class User(Base, TimestampMixin):
    """Represents an authenticated user from OIDC provider."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid)
    oidc_sub: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(Unicode(200), nullable=True)
    groups: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    api_tokens: Mapped[list[APIToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    oauth_codes: Mapped[list[OAuthAuthorizationCode]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(email={self.email!r}, oidc_sub={self.oidc_sub!r})>"
