"""Rate limiting middleware - per-user request limits using slowapi."""

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse


def _get_user_identifier(request: Request) -> str:
    """Extract user identifier for rate limiting.

    Uses authenticated user ID if available, otherwise falls back to IP address.
    """
    # Check for session-based user
    session = getattr(request, "session", None)
    if session:
        user_id = session.get("user_id")
        if user_id:
            return f"user:{user_id}"

    # Check for Bearer token (use hash of token as key)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        import hashlib

        token = auth_header[7:]
        return f"token:{hashlib.sha256(token.encode()).hexdigest()[:16]}"

    # Fall back to IP address
    return get_remote_address(request)


limiter = Limiter(key_func=_get_user_identifier)

# Rate limit decorators for use on endpoints
# Read operations: 1000 per hour
RATE_LIMIT_READ = "1000/hour"
# Write operations: 100 per hour
RATE_LIMIT_WRITE = "100/hour"


def rate_limit_exceeded_handler(_request: Request, exc: RateLimitExceeded) -> Response:
    """Custom handler for rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "retry_after": str(exc.detail),
        },
        headers={"Retry-After": str(exc.detail)},
    )
