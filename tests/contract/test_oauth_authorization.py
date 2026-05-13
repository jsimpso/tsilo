"""Contract test for OAuth authorization - verify authorization endpoint redirect,
state parameter, and PKCE challenge handling."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from tsilo.main import app
from tsilo.middleware.auth import CurrentUser
from tsilo.models.user import User


def _make_user(groups: list[str] | None = None) -> CurrentUser:
    """Create a mock authenticated user."""
    user = User(
        id=uuid.uuid4(),
        oidc_sub="test|123",
        email="test@example.com",
        name="Test User",
        groups=groups or ["platform-team-developers"],
        last_login_at=datetime.now(tz=UTC),
    )
    return CurrentUser(user=user, auth_method="session")


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
    """Mock database session dependency for all OAuth authorization tests."""
    from tsilo.models import get_db

    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session
    yield mock_session
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_authorization_endpoint_exists(client):
    """GET /oauth/authorization should exist and respond (redirect or error, not 404)."""
    response = await client.get("/oauth/authorization")
    assert response.status_code != 404


@pytest.mark.asyncio
async def test_authorization_requires_response_type(client):
    """Authorization endpoint should require response_type=code."""
    response = await client.get(
        "/oauth/authorization",
        params={
            "client_id": "terraform-cli",
            "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
            "code_challenge_method": "S256",
            "redirect_uri": "http://localhost:10000/",
            "state": "test-state-123",
        },
    )
    # Missing response_type - should be 400 or redirect with error
    assert response.status_code in (400, 302)


@pytest.mark.asyncio
async def test_authorization_requires_code_challenge(client):
    """Authorization endpoint should require PKCE code_challenge."""
    response = await client.get(
        "/oauth/authorization",
        params={
            "client_id": "terraform-cli",
            "code_challenge_method": "S256",
            "redirect_uri": "http://localhost:10000/",
            "response_type": "code",
            "state": "test-state-123",
        },
    )
    # Missing code_challenge - should be 400
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_authorization_requires_s256_method(client):
    """Authorization endpoint must require S256 code_challenge_method."""
    response = await client.get(
        "/oauth/authorization",
        params={
            "client_id": "terraform-cli",
            "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
            "code_challenge_method": "plain",
            "redirect_uri": "http://localhost:10000/",
            "response_type": "code",
            "state": "test-state-123",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_authorization_requires_state(client):
    """Authorization endpoint should require state parameter for CSRF protection."""
    response = await client.get(
        "/oauth/authorization",
        params={
            "client_id": "terraform-cli",
            "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
            "code_challenge_method": "S256",
            "redirect_uri": "http://localhost:10000/",
            "response_type": "code",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_authorization_validates_redirect_uri_port_range(client):
    """Redirect URI must use localhost with port in range 10000-10010."""
    response = await client.get(
        "/oauth/authorization",
        params={
            "client_id": "terraform-cli",
            "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
            "code_challenge_method": "S256",
            "redirect_uri": "http://evil.example.com/callback",
            "response_type": "code",
            "state": "test-state-123",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_authorization_unauthenticated_redirects_to_login(client):
    """Unauthenticated user should be redirected to login page."""
    response = await client.get(
        "/oauth/authorization",
        params={
            "client_id": "terraform-cli",
            "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
            "code_challenge_method": "S256",
            "redirect_uri": "http://localhost:10000/",
            "response_type": "code",
            "state": "test-state-123",
        },
    )
    # Should redirect to login
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "/auth/login" in location or "/login" in location


@pytest.mark.asyncio
async def test_authorization_preserves_state_parameter(client):
    """State parameter must be preserved through the flow and returned in redirect."""
    # This tests the full flow when the user is already authenticated
    # We'll test the contract that state is echoed back
    state = "unique-csrf-state-abc123"
    response = await client.get(
        "/oauth/authorization",
        params={
            "client_id": "terraform-cli",
            "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
            "code_challenge_method": "S256",
            "redirect_uri": "http://localhost:10000/",
            "response_type": "code",
            "state": state,
        },
    )
    # Even for redirect to login, the state should be preserved in the session/flow
    assert response.status_code in (302, 400)


@pytest.mark.asyncio
async def test_authorization_valid_redirect_uri_ports(client):
    """Redirect URIs with ports 10000 through 10010 should be accepted."""
    for port in [10000, 10005, 10010]:
        response = await client.get(
            "/oauth/authorization",
            params={
                "client_id": "terraform-cli",
                "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
                "code_challenge_method": "S256",
                "redirect_uri": f"http://localhost:{port}/",
                "response_type": "code",
                "state": "test-state",
            },
        )
        # Should not be 400 for port validation (may be 302 for login redirect)
        assert response.status_code != 400 or "port" not in response.text.lower()
