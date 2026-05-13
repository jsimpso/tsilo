"""FastAPI application entry point - app initialization, middleware, CORS, security headers."""

import hashlib
import hmac
import json
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from tsilo.config import get_settings
from tsilo.middleware.logging import LoggingMiddleware, configure_logging
from tsilo.middleware.rate_limit import limiter

settings = get_settings()

# Configure structured logging
configure_logging(settings.log_level)

app = FastAPI(
    title="Tsilo - Private Terraform Module Registry",
    description="A private Terraform module registry with OIDC authentication and namespace-based access control.",
    version="0.1.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# Rate limiter state
app.state.limiter = limiter

# Exception handlers
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_STATUS_TITLES = {
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
}


@app.exception_handler(HTTPException)
async def terraform_compatible_error_handler(request: Request, exc: HTTPException):
    """Return errors in Terraform-compatible format for registry API endpoints."""
    path = request.url.path
    if path.startswith("/v1/modules/") or path.startswith("/.well-known/"):
        title = _STATUS_TITLES.get(exc.status_code, "Error")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "errors": [
                    {
                        "status": str(exc.status_code),
                        "title": title,
                        "detail": exc.detail,
                    }
                ]
            },
            headers=getattr(exc, "headers", None),
        )
    # For non-registry endpoints, use default format
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


# Middleware (applied in reverse order - last added is outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_base_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="tsilo_session",
    max_age=86400,  # 24 hours
    same_site="lax",
    https_only=not settings.is_development,
)

app.add_middleware(LoggingMiddleware)

# Mount static files
app.mount(
    "/static",
    StaticFiles(directory="src/tsilo/static"),
    name="static",
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not settings.is_development:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def _generate_csrf_token(session_id: str) -> str:
    """Generate a CSRF token tied to the user's session."""
    return hmac.new(
        settings.csrf_secret_key.encode(),
        session_id.encode(),
        hashlib.sha256,
    ).hexdigest()


def _validate_csrf_token(token: str, session_id: str) -> bool:
    """Validate a CSRF token against the session."""
    expected = _generate_csrf_token(session_id)
    return hmac.compare_digest(token, expected)


# Paths exempt from CSRF validation (API token auth or public endpoints)
_CSRF_EXEMPT_PREFIXES = (
    "/v1/modules/",
    "/.well-known/",
    "/health",
    "/metrics",
    "/auth/login",
    "/auth/callback",
)

_CSRF_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    """Validate X-CSRF-Token header for state-changing requests from web UI sessions.

    Bearer token authenticated requests are exempt (API/CI usage).
    """
    if request.method in _CSRF_METHODS:
        path = request.url.path

        # Skip CSRF for exempt paths
        if not any(path.startswith(prefix) for prefix in _CSRF_EXEMPT_PREFIXES):
            # Skip CSRF if request uses Bearer token auth
            auth_header = request.headers.get("authorization", "")
            if not auth_header.lower().startswith("bearer "):
                # Session-based request - require CSRF token
                session = request.session
                session_id = session.get("user_id", "")
                if session_id:
                    csrf_token = request.headers.get("x-csrf-token", "")
                    if not csrf_token or not _validate_csrf_token(csrf_token, session_id):
                        return JSONResponse(
                            status_code=403,
                            content={"detail": "CSRF token missing or invalid"},
                        )

    response = await call_next(request)

    # Inject CSRF token for session-authenticated HTML responses
    session = request.session
    session_id = session.get("user_id", "")
    if session_id:
        response.headers["X-CSRF-Token"] = _generate_csrf_token(session_id)

    return response


# Import and include routers
from tsilo.api.auth import router as auth_router  # noqa: E402
from tsilo.api.metrics import router as metrics_router  # noqa: E402
from tsilo.api.modules import router as modules_router  # noqa: E402
from tsilo.api.namespaces import router as namespaces_router  # noqa: E402
from tsilo.api.registry import router as registry_router  # noqa: E402

app.include_router(auth_router)
app.include_router(metrics_router)
app.include_router(modules_router)
app.include_router(namespaces_router)
app.include_router(registry_router)

STATIC_DIR = Path("src/tsilo/static")


@app.get("/", include_in_schema=False)
async def homepage():
    """Serve the static homepage."""
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")


@app.get("/modules/{namespace}/{name}/{provider}", include_in_schema=False)
@app.get("/modules/{namespace}/{name}/{provider}/{version}", include_in_schema=False)
async def module_detail_page(namespace: str, name: str, provider: str, version: str | None = None):
    """Serve the module detail SPA page (client-side routing)."""
    return FileResponse(STATIC_DIR / "module-detail.html", media_type="text/html")


@app.get("/upload", include_in_schema=False)
async def upload_page():
    """Serve the module upload page."""
    return FileResponse(STATIC_DIR / "upload.html", media_type="text/html")
