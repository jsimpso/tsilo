"""Authentication endpoints - OIDC login, callback, session, logout."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.config import get_settings
from tsilo.middleware.auth import CurrentUser, get_current_user
from tsilo.models import get_db
from tsilo.services.auth_service import AuthService, oauth

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    """Initiate OIDC login flow by redirecting to the OIDC provider."""
    redirect_uri = settings.oidc_redirect_uri
    oidc_client = oauth.create_client("oidc")
    return await oidc_client.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle OIDC authorization code callback.

    Exchanges the code for tokens, creates/updates the user, and sets a session cookie.
    """
    oidc_client = oauth.create_client("oidc")

    try:
        token = await oidc_client.authorize_access_token(request)
    except Exception as exc:
        logger.error("oidc_callback_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange authorization code",
        ) from exc

    userinfo = token.get("userinfo")
    if userinfo is None:
        try:
            userinfo = await oidc_client.userinfo(token=token)
        except Exception as exc:
            logger.error("oidc_userinfo_failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve user info",
            ) from exc

    oidc_sub = userinfo.get("sub")
    if not oidc_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC response missing 'sub' claim",
        )

    email = userinfo.get("email", "")
    name = userinfo.get("name")
    groups = userinfo.get("groups", [])

    auth_service = AuthService(db)
    user = await auth_service.get_or_create_user(
        oidc_sub=oidc_sub,
        email=email,
        name=name,
        groups=groups,
    )

    # Store user ID in session
    request.session["user_id"] = str(user.id)

    logger.info(
        "user_logged_in",
        user_id=str(user.id),
        email=email,
        auth_method="oidc",
    )

    return RedirectResponse(url="/", status_code=302)


@router.post("/logout")
async def logout(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Terminate user session and clear the session cookie."""
    logger.info(
        "user_logged_out",
        user_id=str(current_user.id),
        email=current_user.email,
    )

    request.session.clear()
    return JSONResponse(
        content={"message": "Logged out successfully"},
        status_code=200,
    )


@router.get("/me")
async def me(current_user: CurrentUser = Depends(get_current_user)):
    """Get current authenticated user information."""
    from tsilo.services.permission_service import PermissionService
    from tsilo.models import get_db as _get_db

    return JSONResponse(
        content={
            "user": {
                "id": str(current_user.id),
                "email": current_user.email,
                "name": current_user.user.name,
                "groups": current_user.groups,
            },
        },
        status_code=200,
    )
