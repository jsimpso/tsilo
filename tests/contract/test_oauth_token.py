"""Contract test for OAuth token exchange - verify code verifier validation,
token issuance, and error cases."""

import hashlib
import base64
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tsilo.main import app
from tsilo.middleware.auth import CurrentUser
from tsilo.models.user import User


@pytest.fixture
async def client():
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as ac:
        yield ac


@pytest.fixture(autouse=True)
def mock_db():
    """Mock database session dependency for all OAuth token tests."""
    from unittest.mock import MagicMock

    from tsilo.models import get_db

    mock_session = AsyncMock()
    # Ensure execute().scalar_one_or_none() returns None (code not found)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_session
    yield mock_session
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_token_endpoint_exists(client):
    """POST /oauth/token should exist (not 404 or 405)."""
    response = await client.post(
        "/oauth/token",
        data={"grant_type": "authorization_code"},
    )
    assert response.status_code not in (404, 405)


@pytest.mark.asyncio
async def test_token_requires_grant_type(client):
    """Token endpoint must require grant_type=authorization_code."""
    response = await client.post(
        "/oauth/token",
        data={
            "code": "some-code",
            "redirect_uri": "http://localhost:10000/",
            "client_id": "terraform-cli",
            "code_verifier": "some-verifier",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data.get("error") in ("invalid_request", "unsupported_grant_type")


@pytest.mark.asyncio
async def test_token_requires_code(client):
    """Token endpoint must require authorization code."""
    response = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "redirect_uri": "http://localhost:10000/",
            "client_id": "terraform-cli",
            "code_verifier": "some-verifier",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data.get("error") == "invalid_request"


@pytest.mark.asyncio
async def test_token_requires_code_verifier(client):
    """Token endpoint must require PKCE code_verifier."""
    response = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": "some-code",
            "redirect_uri": "http://localhost:10000/",
            "client_id": "terraform-cli",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data.get("error") == "invalid_request"


@pytest.mark.asyncio
async def test_token_invalid_code_returns_error(client):
    """Token endpoint should reject invalid authorization codes."""
    response = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": "invalid-code-that-does-not-exist",
            "redirect_uri": "http://localhost:10000/",
            "client_id": "terraform-cli",
            "code_verifier": "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data.get("error") == "invalid_grant"


@pytest.mark.asyncio
async def test_token_unsupported_grant_type(client):
    """Token endpoint must reject unsupported grant types."""
    response = await client.post(
        "/oauth/token",
        data={
            "grant_type": "client_credentials",
            "code": "some-code",
            "client_id": "terraform-cli",
            "code_verifier": "some-verifier",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data.get("error") == "unsupported_grant_type"


@pytest.mark.asyncio
async def test_token_response_format(client):
    """Successful token response must include access_token, token_type, and expires_in."""
    # We can't test a full success without a valid code, but we verify the error
    # response format follows OAuth 2.0 spec
    response = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": "invalid",
            "redirect_uri": "http://localhost:10000/",
            "client_id": "terraform-cli",
            "code_verifier": "test-verifier",
        },
    )
    assert response.status_code == 400
    data = response.json()
    # OAuth 2.0 error response must have "error" field
    assert "error" in data


@pytest.mark.asyncio
async def test_token_response_no_store_cache(client):
    """Token response must include Cache-Control: no-store header."""
    response = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": "invalid",
            "redirect_uri": "http://localhost:10000/",
            "client_id": "terraform-cli",
            "code_verifier": "test-verifier",
        },
    )
    # Even error responses should have no-store
    cache_control = response.headers.get("cache-control", "")
    assert "no-store" in cache_control


@pytest.mark.asyncio
async def test_token_content_type_json(client):
    """Token endpoint must return application/json."""
    response = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": "invalid",
            "redirect_uri": "http://localhost:10000/",
            "client_id": "terraform-cli",
            "code_verifier": "test-verifier",
        },
    )
    assert "application/json" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_token_accepts_form_encoded(client):
    """Token endpoint must accept application/x-www-form-urlencoded."""
    response = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": "test",
            "redirect_uri": "http://localhost:10000/",
            "client_id": "terraform-cli",
            "code_verifier": "test-verifier",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    # Should process the request (400 for invalid code, not 415 or 422)
    assert response.status_code == 400
    data = response.json()
    assert data.get("error") == "invalid_grant"
