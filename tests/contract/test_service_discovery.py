"""Contract test for service discovery - verify /.well-known/terraform.json structure."""

import pytest
from httpx import ASGITransport, AsyncClient

from tsilo.main import app


@pytest.fixture
async def client():
    """Create an async test client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_service_discovery_returns_modules_v1(client):
    """Service discovery must return modules.v1 pointing to /v1/modules/."""
    response = await client.get("/.well-known/terraform.json")
    assert response.status_code == 200
    data = response.json()
    assert "modules.v1" in data
    assert data["modules.v1"] == "/v1/modules/"


@pytest.mark.asyncio
async def test_service_discovery_returns_login_v1(client):
    """Service discovery must return login.v1 with OAuth configuration."""
    response = await client.get("/.well-known/terraform.json")
    assert response.status_code == 200
    data = response.json()
    assert "login.v1" in data
    login = data["login.v1"]
    assert login["client"] == "terraform-cli"
    assert login["grant_types"] == ["authz_code"]
    assert login["authz"] == "/oauth/authorization"
    assert login["token"] == "/oauth/token"  # noqa: S105
    assert login["ports"] == [10000, 10010]


@pytest.mark.asyncio
async def test_service_discovery_no_auth_required(client):
    """Service discovery must be accessible without authentication."""
    response = await client.get("/.well-known/terraform.json")
    # No Authorization header sent - should still return 200
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_service_discovery_content_type(client):
    """Service discovery must return application/json content type."""
    response = await client.get("/.well-known/terraform.json")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_service_discovery_cacheable(client):
    """Service discovery response should be cacheable."""
    response = await client.get("/.well-known/terraform.json")
    assert response.status_code == 200
    cache_control = response.headers.get("cache-control", "")
    assert "public" in cache_control
    assert "max-age" in cache_control
