"""API token management endpoints - list, create, revoke tokens."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.middleware.auth import CurrentUser, get_current_user
from tsilo.models import get_db
from tsilo.schemas.api_token import (
    TokenCreate,
    TokenCreatedInfo,
    TokenCreateResponse,
    TokenInfo,
    TokenListResponse,
    TokenScopeEntry,
)
from tsilo.services.token_service import TokenService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/tokens", tags=["tokens"])


@router.get("")
async def list_tokens(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """List all active API tokens for the current user.

    Token values are never returned - only metadata.
    """
    token_service = TokenService(db)
    tokens = await token_service.list_user_tokens(current_user.id)

    token_list = [
        TokenInfo(
            id=t.id,
            name=t.name,
            scopes=[TokenScopeEntry(**s) for s in t.scopes] if t.scopes else [],
            last_used_at=t.last_used_at,
            expires_at=t.expires_at,
            created_at=t.created_at,
        )
        for t in tokens
    ]

    response = TokenListResponse(tokens=token_list)
    return JSONResponse(
        content=response.model_dump(mode="json"),
        status_code=200,
    )


@router.post("", status_code=201)
async def create_token(
    body: TokenCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Create a new API token.

    Returns the plaintext token value exactly once.
    The caller must save it immediately - it cannot be retrieved later.
    """
    token_service = TokenService(db)
    api_token, plaintext = await token_service.create_token(
        user_id=current_user.id,
        name=body.name,
        scopes=[s.model_dump() for s in body.scopes],
        expires_in_days=body.expires_in_days,
    )

    logger.info(
        "api_token_created_via_ui",
        user_id=str(current_user.id),
        token_id=str(api_token.id),
        name=body.name,
    )

    response = TokenCreateResponse(
        token=TokenCreatedInfo(
            id=api_token.id,
            name=api_token.name,
            token_value=plaintext,
            scopes=[TokenScopeEntry(**s) for s in api_token.scopes] if api_token.scopes else [],
            expires_at=api_token.expires_at,
            created_at=api_token.created_at,
        ),
    )
    return JSONResponse(
        content=response.model_dump(mode="json"),
        status_code=201,
    )


@router.delete("/{token_id}", status_code=204)
async def revoke_token(
    token_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Revoke an API token by setting its revoked_at timestamp.

    Only the token's owner can revoke it.
    """
    token_service = TokenService(db)
    token = await token_service.revoke_token(token_id, current_user.id)

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )

    logger.info(
        "api_token_revoked_via_ui",
        user_id=str(current_user.id),
        token_id=str(token_id),
    )

    return Response(status_code=204)
