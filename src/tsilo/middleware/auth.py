"""Authentication middleware - Bearer token and session cookie validation."""

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.models import get_db
from tsilo.models.api_token import APIToken
from tsilo.models.user import User
from tsilo.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser:
    """Represents the authenticated user context for a request."""

    def __init__(self, user: User, auth_method: str = "session") -> None:
        self.user = user
        self.id = user.id
        self.email = user.email
        self.groups: list[str] = user.groups or []
        self.auth_method = auth_method


async def _authenticate_bearer_token(token: str, db: AsyncSession) -> CurrentUser | None:
    """Authenticate via API token (Bearer token in Authorization header)."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = select(APIToken).where(APIToken.token_hash == token_hash)
    result = await db.execute(stmt)
    api_token = result.scalar_one_or_none()

    if api_token is None:
        return None

    if not api_token.is_valid:
        return None

    # Update last_used_at
    api_token.last_used_at = datetime.now(tz=timezone.utc)

    # Load the user
    user_stmt = select(User).where(User.id == api_token.user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if user is None:
        return None

    return CurrentUser(user=user, auth_method="api_token")


async def _authenticate_session(request: Request, db: AsyncSession) -> CurrentUser | None:
    """Authenticate via session cookie."""
    session = request.session
    user_id = session.get("user_id")
    if not user_id:
        return None

    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        return None

    stmt = select(User).where(User.id == uid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return None

    return CurrentUser(user=user, auth_method="session")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """FastAPI dependency that extracts and validates the current user.

    Supports:
    - Bearer token (API tokens for CI/CD)
    - Session cookie (web UI login)

    Raises HTTPException 401 if no valid authentication is found.
    """
    # Try Bearer token first
    if credentials is not None:
        user = await _authenticate_bearer_token(credentials.credentials, db)
        if user is not None:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Try session cookie
    user = await _authenticate_session(request, db)
    if user is not None:
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser | None:
    """Like get_current_user but returns None instead of raising 401."""
    if credentials is not None:
        return await _authenticate_bearer_token(credentials.credentials, db)
    return await _authenticate_session(request, db)
