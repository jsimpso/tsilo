"""FastAPI application entry point - app initialization, middleware, CORS, security headers."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


# Import and include routers
from tsilo.api.metrics import router as metrics_router  # noqa: E402
from tsilo.api.registry import router as registry_router  # noqa: E402

app.include_router(metrics_router)
app.include_router(registry_router)
