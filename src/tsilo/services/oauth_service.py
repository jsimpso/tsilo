"""OAuth service - authorization code generation, PKCE validation, code storage."""

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import structlog
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.models.oauth_code import OAuthAuthorizationCode

logger = structlog.get_logger(__name__)

# Authorization codes expire after 10 minutes per spec
AUTH_CODE_LIFETIME = timedelta(minutes=10)

# Valid redirect URI port range per Terraform CLI login protocol
VALID_PORT_MIN = 10000
VALID_PORT_MAX = 10010


def validate_redirect_uri(redirect_uri: str) -> bool:
    """Validate that redirect_uri is a localhost URL with port in range 10000-10010."""
    try:
        parsed = urlparse(redirect_uri)
    except Exception:
        return False

    if parsed.scheme != "http":
        return False

    if parsed.hostname not in ("localhost", "127.0.0.1"):
        return False

    if parsed.port is None:
        return False

    return VALID_PORT_MIN <= parsed.port <= VALID_PORT_MAX


def validate_pkce_challenge(code_verifier: str, code_challenge: str) -> bool:
    """Validate PKCE: SHA256(code_verifier) must equal stored code_challenge.

    Per RFC 7636, the S256 method computes:
        code_challenge = BASE64URL(SHA256(code_verifier))
    """
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return secrets.compare_digest(computed, code_challenge)


class OAuthService:
    """Manages OAuth authorization codes for the Terraform CLI login flow."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def generate_authorization_code(
        self,
        user_id: uuid.UUID,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        scopes: list[str] | None = None,
    ) -> str:
        """Generate and store a new authorization code.

        Returns the plaintext authorization code string.
        """
        code = secrets.token_urlsafe(48)
        expires_at = datetime.now(tz=timezone.utc) + AUTH_CODE_LIFETIME

        auth_code = OAuthAuthorizationCode(
            code=code,
            user_id=user_id,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scopes=scopes or [],
            expires_at=expires_at,
        )
        self._db.add(auth_code)
        await self._db.flush()

        logger.info(
            "oauth_code_generated",
            user_id=str(user_id),
            client_id=client_id,
            expires_at=expires_at.isoformat(),
        )
        return code

    async def exchange_code(
        self,
        code: str,
        client_id: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> OAuthAuthorizationCode:
        """Exchange an authorization code for user context after PKCE validation.

        Validates:
        - Code exists and is not expired
        - Code has not already been used (single-use)
        - client_id matches
        - redirect_uri matches
        - PKCE code_verifier matches stored code_challenge

        Returns the OAuthAuthorizationCode record on success.
        Raises ValueError on any validation failure.
        """
        stmt = select(OAuthAuthorizationCode).where(
            OAuthAuthorizationCode.code == code,
        )
        result = await self._db.execute(stmt)
        auth_code = result.scalar_one_or_none()

        if auth_code is None:
            raise ValueError("Authorization code not found")

        # Check if already used
        if auth_code.used_at is not None:
            logger.warning(
                "oauth_code_reuse_attempt",
                code_id=str(auth_code.id),
                user_id=str(auth_code.user_id),
            )
            raise ValueError("Authorization code has already been used")

        # Check expiration
        now = datetime.now(tz=timezone.utc)
        if auth_code.expires_at <= now:
            raise ValueError("Authorization code has expired")

        # Validate client_id
        if auth_code.client_id != client_id:
            raise ValueError("Client ID mismatch")

        # Validate redirect_uri
        if auth_code.redirect_uri != redirect_uri:
            raise ValueError("Redirect URI mismatch")

        # Validate PKCE code_verifier against stored code_challenge
        if not validate_pkce_challenge(code_verifier, auth_code.code_challenge):
            logger.warning(
                "oauth_pkce_mismatch",
                code_id=str(auth_code.id),
                user_id=str(auth_code.user_id),
            )
            raise ValueError("Code verifier does not match code challenge")

        # Mark code as used
        auth_code.used_at = now
        await self._db.flush()

        logger.info(
            "oauth_code_exchanged",
            code_id=str(auth_code.id),
            user_id=str(auth_code.user_id),
            client_id=client_id,
        )
        return auth_code

    async def cleanup_expired_codes(self) -> int:
        """Delete expired and old used authorization codes.

        Removes:
        - Codes expired more than 24 hours ago
        - Used codes older than 7 days

        Returns the number of deleted records.
        """
        now = datetime.now(tz=timezone.utc)
        expired_cutoff = now - timedelta(hours=24)
        used_cutoff = now - timedelta(days=7)

        stmt = delete(OAuthAuthorizationCode).where(
            (OAuthAuthorizationCode.expires_at < expired_cutoff)
            | (
                OAuthAuthorizationCode.used_at.isnot(None)
                & (OAuthAuthorizationCode.used_at < used_cutoff)
            )
        )
        result = await self._db.execute(stmt)
        await self._db.flush()

        count = result.rowcount
        if count > 0:
            logger.info("oauth_codes_cleaned_up", deleted_count=count)
        return count
