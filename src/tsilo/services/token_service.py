"""Token service - generate, hash, validate, and manage API tokens."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.models.api_token import APIToken

logger = structlog.get_logger(__name__)

TOKEN_PREFIX = "tsilo_"  # noqa: S105


def generate_token() -> str:
    """Generate a cryptographically random API token with prefix.

    Returns a string like 'tsilo_<random>' that is 64 characters total.
    """
    random_part = secrets.token_urlsafe(42)
    return f"{TOKEN_PREFIX}{random_part}"


def hash_token(token: str) -> str:
    """Hash a plaintext token using SHA256 for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


class TokenService:
    """Manages API token lifecycle: create, list, revoke, validate."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_token(
        self,
        user_id: uuid.UUID,
        name: str,
        scopes: list[dict[str, Any]] | None = None,
        expires_in_days: int | None = None,
    ) -> tuple[APIToken, str]:
        """Create a new API token for a user.

        Returns:
            Tuple of (APIToken record, plaintext token value).
            The plaintext value is only available at creation time.
        """
        plaintext = generate_token()
        token_hash_value = hash_token(plaintext)

        if expires_in_days is not None:
            expires_at = datetime.now(tz=UTC) + timedelta(days=expires_in_days)
        else:
            # Far-future expiry for tokens without explicit expiration
            expires_at = datetime.now(tz=UTC) + timedelta(days=36500)

        token = APIToken(
            token_hash=token_hash_value,
            user_id=user_id,
            name=name,
            scopes=scopes or [],
            expires_at=expires_at,
        )
        self._db.add(token)
        await self._db.flush()

        logger.info(
            "api_token_created",
            token_id=str(token.id),
            user_id=str(user_id),
            name=name,
            expires_at=expires_at.isoformat(),
        )
        return token, plaintext

    async def list_user_tokens(self, user_id: uuid.UUID) -> list[APIToken]:
        """List all non-revoked tokens for a user."""
        stmt = (
            select(APIToken)
            .where(
                APIToken.user_id == user_id,
                APIToken.revoked_at.is_(None),
            )
            .order_by(APIToken.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_token_by_id(self, token_id: uuid.UUID, user_id: uuid.UUID) -> APIToken | None:
        """Get a token by ID, scoped to the owning user."""
        stmt = select(APIToken).where(
            APIToken.id == token_id,
            APIToken.user_id == user_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_token(self, token_id: uuid.UUID, user_id: uuid.UUID) -> APIToken | None:
        """Revoke a token by setting revoked_at timestamp.

        Returns the token if found and revoked, None if not found or not owned by user.
        """
        token = await self.get_token_by_id(token_id, user_id)
        if token is None:
            return None

        if token.revoked_at is not None:
            return token  # Already revoked

        token.revoked_at = datetime.now(tz=UTC)
        await self._db.flush()

        logger.info(
            "api_token_revoked",
            token_id=str(token_id),
            user_id=str(user_id),
            name=token.name,
        )
        return token
