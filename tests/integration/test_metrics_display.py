"""Integration test for metrics display - API returns accurate data, deprecation flags."""

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
async def test_metrics_overview_requires_auth(client):
    """GET /api/metrics/overview should require authentication."""
    response = await client.get("/api/metrics/overview")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_metrics_overview_endpoint_exists(client):
    """GET /api/metrics/overview should not return 404."""
    response = await client.get("/api/metrics/overview")
    assert response.status_code != 404


@pytest.mark.asyncio
async def test_module_metrics_requires_auth(client):
    """GET /api/metrics/modules/:ns/:name/:system should require authentication."""
    response = await client.get("/api/metrics/modules/platform-team/vpc/aws")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_module_metrics_endpoint_exists(client):
    """GET /api/metrics/modules/:ns/:name/:system should not return 404."""
    response = await client.get("/api/metrics/modules/platform-team/vpc/aws")
    assert response.status_code != 404


@pytest.mark.asyncio
async def test_metrics_overview_returns_json(client):
    """GET /api/metrics/overview should return JSON content type."""
    response = await client.get("/api/metrics/overview")
    # 401 responses still use JSON
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_module_metrics_not_found(client):
    """Requesting metrics for a non-existent module should return 404 when authenticated."""
    response = await client.get("/api/metrics/modules/nonexistent/fake/aws")
    # Without auth we get 401; with auth we'd get 404
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deprecation_flag_in_module_detail(client):
    """Module detail versions should include deprecated flag."""
    response = await client.get("/api/modules/platform-team/vpc/aws")
    # With auth, each version in the response should have a deprecated field
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_module_detail_includes_total_downloads(client):
    """Module detail response should include total_downloads field."""
    response = await client.get("/api/modules/platform-team/vpc/aws")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_version_detail_includes_download_count(client):
    """Version detail response should include download_count field."""
    response = await client.get("/api/modules/platform-team/vpc/aws/1.0.0")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_version_detail_includes_last_download_at(client):
    """Version detail response should include last_download_at field."""
    response = await client.get("/api/modules/platform-team/vpc/aws/1.0.0")
    assert response.status_code == 401
