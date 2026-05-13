"""Pydantic schemas for OAuth 2.0 - authorization request, token request/response, PKCE."""

from pydantic import BaseModel, Field


class AuthorizationRequest(BaseModel):
    """Query parameters for GET /oauth/authorization."""

    client_id: str = Field(..., description="OAuth client identifier")
    code_challenge: str = Field(..., description="PKCE code challenge (SHA256)")
    code_challenge_method: str = Field(..., description="PKCE method (must be S256)")
    redirect_uri: str = Field(..., description="Callback URL for authorization code")
    response_type: str = Field(..., description="OAuth response type (must be 'code')")
    state: str = Field(..., description="CSRF protection state parameter")


class TokenRequest(BaseModel):
    """Form parameters for POST /oauth/token."""

    grant_type: str = Field(..., description="OAuth grant type (must be 'authorization_code')")
    code: str = Field(..., description="Authorization code from authorization endpoint")
    redirect_uri: str = Field(..., description="Same redirect_uri used in authorization request")
    client_id: str = Field(..., description="OAuth client identifier")
    code_verifier: str = Field(..., description="PKCE code verifier (plaintext)")


class TokenResponse(BaseModel):
    """Response for successful POST /oauth/token."""

    access_token: str = Field(..., description="API access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int | None = Field(
        default=None,
        description="Token lifetime in seconds (null = no expiry)",
    )


class OAuthError(BaseModel):
    """OAuth 2.0 error response per RFC 6749."""

    error: str = Field(..., description="Error code")
    error_description: str | None = Field(
        default=None,
        description="Human-readable error description",
    )
