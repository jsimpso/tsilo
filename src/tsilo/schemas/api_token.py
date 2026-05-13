"""Pydantic schemas for API token management - create, list, revoke."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TokenScopeEntry(BaseModel):
    """A single scope entry for an API token."""

    namespace: str = Field(..., description="Namespace the scope applies to")
    permission: str = Field(
        ...,
        pattern=r"^(read|write)$",
        description="Permission level: 'read' or 'write'",
    )


class TokenCreate(BaseModel):
    """Request body for POST /api/tokens."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable token name",
    )
    scopes: list[TokenScopeEntry] = Field(
        default_factory=list,
        description="List of namespace permissions for this token",
    )
    expires_in_days: int | None = Field(
        default=None,
        ge=1,
        le=3650,
        description="Token lifetime in days (null = no expiry for OAuth tokens)",
    )


class TokenInfo(BaseModel):
    """Token information returned in list responses (no plaintext value)."""

    id: uuid.UUID
    name: str
    scopes: list[TokenScopeEntry]
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime


class TokenCreateResponse(BaseModel):
    """Response for POST /api/tokens - includes plaintext value (shown once)."""

    token: "TokenCreatedInfo"
    warning: str = "Save this token now. You won't be able to see it again!"


class TokenCreatedInfo(BaseModel):
    """Token info with plaintext value, returned only at creation time."""

    id: uuid.UUID
    name: str
    token_value: str = Field(..., description="Plaintext token value (shown once only)")
    scopes: list[TokenScopeEntry]
    expires_at: datetime | None = None
    created_at: datetime


class TokenListResponse(BaseModel):
    """Response for GET /api/tokens."""

    tokens: list[TokenInfo]
