"""OAuthAuthorizationCode model - temporary OAuth 2.0 authorization codes for PKCE flow."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tsilo.models import Base, generate_uuid


class OAuthAuthorizationCode(Base):
    """Temporary storage for OAuth 2.0 authorization codes used in Terraform CLI login with PKCE."""

    __tablename__ = "oauth_authorization_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid)
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(200), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    code_challenge_method: Mapped[str] = mapped_column(String(10), nullable=False, default="S256")
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")

    # Relationships
    user: Mapped["User"] = relationship(back_populates="oauth_codes")  # noqa: F821

    @property
    def is_valid(self) -> bool:
        """Check if code is still valid (not used and not expired)."""
        from datetime import timezone

        now = datetime.now(tz=timezone.utc)
        return self.used_at is None and self.expires_at > now

    def __repr__(self) -> str:
        return f"<OAuthAuthorizationCode(client_id={self.client_id!r}, user_id={self.user_id})>"
