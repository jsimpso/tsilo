"""OIDC authentication service - OAuth client configuration and token validation."""

from datetime import datetime, timezone

import httpx
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.config import get_settings
from tsilo.models.user import User

settings = get_settings()

oauth = OAuth()
oauth.register(
    name="oidc",
    client_id=settings.oidc_client_id,
    client_secret=settings.oidc_client_secret,
    server_metadata_url=f"{settings.oidc_issuer}/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile groups"},
)


class AuthService:
    """Handles OIDC authentication, user creation/update, and token validation."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_or_create_user(
        self,
        oidc_sub: str,
        email: str,
        name: str | None = None,
        groups: list[str] | None = None,
    ) -> User:
        """Get existing user or create a new one from OIDC claims.

        Updates user info (email, name, groups, last_login_at) on each login.
        """
        stmt = select(User).where(User.oidc_sub == oidc_sub)
        result = await self._db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                oidc_sub=oidc_sub,
                email=email,
                name=name,
                groups=groups or [],
                last_login_at=datetime.now(tz=timezone.utc),
            )
            self._db.add(user)
        else:
            user.email = email
            user.name = name
            user.groups = groups or []
            user.last_login_at = datetime.now(tz=timezone.utc)

        await self._db.flush()
        return user

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by their database ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def validate_oidc_token(self, token: str) -> dict | None:
        """Validate an OIDC access token by calling the userinfo endpoint.

        Returns the user info claims dict or None if invalid.
        """
        try:
            metadata_url = f"{settings.oidc_issuer}/.well-known/openid-configuration"
            async with httpx.AsyncClient() as client:
                metadata_resp = await client.get(metadata_url)
                metadata_resp.raise_for_status()
                metadata = metadata_resp.json()

                userinfo_url = metadata.get("userinfo_endpoint")
                if not userinfo_url:
                    return None

                resp = await client.get(
                    userinfo_url,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return None

    @staticmethod
    def check_connectivity() -> bool:
        """Check if the OIDC provider is reachable."""
        try:
            resp = httpx.get(
                f"{settings.oidc_issuer}/.well-known/openid-configuration",
                timeout=5.0,
            )
            return resp.status_code == 200
        except Exception:
            return False
