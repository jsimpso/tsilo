"""Authentication endpoints - OIDC login, callback, session, logout, OAuth 2.0."""

import json
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.config import get_settings
from tsilo.middleware.auth import CurrentUser, get_current_user
from tsilo.models import get_db
from tsilo.services.auth_service import AuthService, oauth
from tsilo.services.oauth_service import OAuthService, validate_redirect_uri

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

    # Check if there's a pending OAuth authorization request (Terraform CLI login)
    oauth_request = request.session.pop("oauth_request", None)
    if oauth_request:
        params = urlencode(
            {
                "client_id": oauth_request["client_id"],
                "code_challenge": oauth_request["code_challenge"],
                "code_challenge_method": oauth_request["code_challenge_method"],
                "redirect_uri": oauth_request["redirect_uri"],
                "response_type": "code",
                "state": oauth_request["state"],
            }
        )
        return RedirectResponse(url=f"/oauth/authorization?{params}", status_code=302)

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


# --- OAuth 2.0 endpoints for Terraform CLI login ---

oauth_router = APIRouter(prefix="/oauth", tags=["oauth"])


@oauth_router.get("/authorization")
async def oauth_authorization(
    request: Request,
    client_id: str | None = None,
    code_challenge: str | None = None,
    code_challenge_method: str | None = None,
    redirect_uri: str | None = None,
    response_type: str | None = None,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """OAuth 2.0 authorization endpoint for Terraform CLI login.

    Validates parameters, redirects unauthenticated users to OIDC login,
    then generates an authorization code and redirects back to the CLI.
    """
    # Validate required parameters
    if not response_type or response_type != "code":
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_request",
                "error_description": "response_type must be 'code'",
            },
        )

    if not code_challenge:
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_request",
                "error_description": "code_challenge is required for PKCE",
            },
        )

    if not code_challenge_method or code_challenge_method != "S256":
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_request",
                "error_description": "code_challenge_method must be 'S256'",
            },
        )

    if not state:
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_request",
                "error_description": "state parameter is required",
            },
        )

    if not redirect_uri or not validate_redirect_uri(redirect_uri):
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_request",
                "error_description": (
                    "redirect_uri must be http://localhost" " with port in range 10000-10010"
                ),
            },
        )

    # Store OAuth request in session for after OIDC login
    request.session["oauth_request"] = {
        "client_id": client_id or "terraform-cli",
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "redirect_uri": redirect_uri,
        "state": state,
    }

    # Check if user is already authenticated
    user_id = request.session.get("user_id")
    if not user_id:
        # Redirect to OIDC login; after login, callback will check for oauth_request
        login_url = "/auth/login"
        return RedirectResponse(url=login_url, status_code=302)

    # User is authenticated - generate authorization code
    oauth_service = OAuthService(db)
    code = await oauth_service.generate_authorization_code(
        user_id=user_id,
        client_id=client_id or "terraform-cli",
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )

    # Redirect back to CLI with code and state
    params = urlencode({"code": code, "state": state})
    return RedirectResponse(url=f"{redirect_uri}?{params}", status_code=302)


@oauth_router.post("/token")
async def oauth_token(
    grant_type: str = Form(default=None),
    code: str = Form(default=None),
    redirect_uri: str = Form(default=None),
    client_id: str = Form(default=None),
    code_verifier: str = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """OAuth 2.0 token endpoint - exchange authorization code for access token.

    Validates PKCE code_verifier against the stored code_challenge,
    then creates an API token for the user.
    """
    # Validate grant_type
    if not grant_type:
        return _oauth_error("invalid_request", "grant_type is required", 400)
    if grant_type != "authorization_code":
        return _oauth_error("unsupported_grant_type", f"Unsupported grant type: {grant_type}", 400)

    # Validate required fields
    if not code:
        return _oauth_error("invalid_request", "code is required", 400)
    if not code_verifier:
        return _oauth_error("invalid_request", "code_verifier is required for PKCE", 400)

    # Exchange the authorization code (validates PKCE, single-use, expiry)
    oauth_service = OAuthService(db)
    try:
        auth_code = await oauth_service.exchange_code(
            code=code,
            client_id=client_id or "terraform-cli",
            redirect_uri=redirect_uri or "",
            code_verifier=code_verifier,
        )
    except ValueError as e:
        error_msg = str(e)
        logger.warning("oauth_token_exchange_failed", error=error_msg)
        return _oauth_error("invalid_grant", error_msg, 400)

    # Create an API token for the user (no expiry per Terraform CLI spec)
    from tsilo.services.token_service import TokenService

    token_service = TokenService(db)
    api_token, plaintext = await token_service.create_token(
        user_id=auth_code.user_id,
        name=f"Terraform CLI ({client_id or 'terraform-cli'})",
        scopes=auth_code.scopes,
        expires_in_days=None,  # No expiry for Terraform CLI tokens
    )

    logger.info(
        "oauth_token_issued",
        user_id=str(auth_code.user_id),
        client_id=client_id,
        token_id=str(api_token.id),
    )

    response_data = json.dumps(
        {
            "access_token": plaintext,
            "token_type": "Bearer",
            "expires_in": None,
        }
    )
    return Response(
        content=response_data,
        status_code=200,
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )


def _oauth_error(error: str, description: str, status_code: int) -> Response:
    """Return an OAuth 2.0 error response per RFC 6749."""
    return Response(
        content=json.dumps(
            {
                "error": error,
                "error_description": description,
            }
        ),
        status_code=status_code,
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )
