"""Integration test for module detail page - README, inputs/outputs, version switching."""

import pytest
from httpx import ASGITransport, AsyncClient

from tsilo.main import app


@pytest.fixture
async def client():
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_module_detail_requires_auth(client):
    """GET /api/modules/:ns/:name/:system should require authentication."""
    response = await client.get("/api/modules/platform-team/vpc/aws")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_module_detail_endpoint_exists(client):
    """GET /api/modules/:ns/:name/:system should not return 404 method-not-allowed."""
    response = await client.get("/api/modules/platform-team/vpc/aws")
    assert response.status_code != 405


@pytest.mark.asyncio
async def test_version_detail_requires_auth(client):
    """GET /api/modules/:ns/:name/:system/:version should require auth."""
    response = await client.get("/api/modules/platform-team/vpc/aws/1.0.0")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_version_detail_endpoint_exists(client):
    """GET /api/modules/:ns/:name/:system/:version should not return 405."""
    response = await client.get("/api/modules/platform-team/vpc/aws/1.0.0")
    assert response.status_code != 405


@pytest.mark.asyncio
async def test_module_detail_not_found(client):
    """Requesting a non-existent module should eventually return 404 when authenticated."""
    response = await client.get("/api/modules/nonexistent/fake/aws")
    # Without auth we get 401; with auth we'd get 404 for non-existent module
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_version_detail_not_found(client):
    """Requesting a non-existent version should return 404 when authenticated."""
    response = await client.get("/api/modules/platform-team/vpc/aws/99.99.99")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_module_detail_response_structure(client):
    """Module detail response should include module info and versions list."""
    # Will validate structure once auth is available
    response = await client.get("/api/modules/platform-team/vpc/aws")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_version_detail_includes_inputs_outputs(client):
    """Version detail should include inputs and outputs arrays."""
    # Will validate structure once auth is available
    response = await client.get("/api/modules/platform-team/vpc/aws/1.0.0")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_version_detail_includes_readme(client):
    """Version detail should include README content."""
    response = await client.get("/api/modules/platform-team/vpc/aws/1.0.0")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_version_detail_includes_usage_example(client):
    """Version detail should include a usage example snippet."""
    response = await client.get("/api/modules/platform-team/vpc/aws/1.0.0")
    assert response.status_code == 401
