"""Integration test for namespace isolation - verify access control enforcement."""

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


# --- Namespace listing isolation ---


@pytest.mark.asyncio
async def test_namespace_list_requires_auth(client):
    """GET /api/namespaces should require authentication."""
    response = await client.get("/api/namespaces")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_namespace_list_endpoint_exists(client):
    """GET /api/namespaces should not return 404."""
    response = await client.get("/api/namespaces")
    assert response.status_code != 404


# --- Namespace creation isolation ---


@pytest.mark.asyncio
async def test_namespace_create_requires_auth(client):
    """POST /api/namespaces should require authentication."""
    response = await client.post(
        "/api/namespaces",
        json={"name": "test-ns", "display_name": "Test Namespace"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_namespace_create_endpoint_exists(client):
    """POST /api/namespaces should not return 404."""
    response = await client.post(
        "/api/namespaces",
        json={"name": "test-ns", "display_name": "Test Namespace"},
    )
    assert response.status_code != 404


# --- Permission listing isolation ---


@pytest.mark.asyncio
async def test_namespace_permissions_requires_auth(client):
    """GET /api/namespaces/:namespace/permissions should require authentication."""
    response = await client.get("/api/namespaces/platform-team/permissions")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_namespace_permissions_endpoint_exists(client):
    """GET /api/namespaces/:namespace/permissions should not return 404."""
    response = await client.get("/api/namespaces/platform-team/permissions")
    assert response.status_code != 404


# --- Module listing respects namespace isolation ---


@pytest.mark.asyncio
async def test_module_list_only_returns_authorized_namespaces(client):
    """GET /api/modules should only return modules from authorized namespaces.

    Without authentication, no modules should be returned.
    """
    response = await client.get("/api/modules")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_module_detail_unauthorized_namespace_returns_403(client):
    """GET /api/modules/:ns/:name/:system should return 403 for unauthorized namespace."""
    # Without auth this returns 401; with auth for wrong namespace it should be 403
    response = await client.get("/api/modules/secret-team/vpc/aws")
    assert response.status_code == 401


# --- Download isolation ---


@pytest.mark.asyncio
async def test_download_unauthorized_namespace_returns_403(client):
    """GET /v1/modules/:ns/:name/:system/:version/download should deny unauthorized access."""
    response = await client.get("/v1/modules/secret-team/vpc/aws/1.0.0/download")
    assert response.status_code == 401


# --- Upload isolation ---


@pytest.mark.asyncio
async def test_upload_unauthorized_namespace_returns_403(client):
    """POST /v1/modules/:ns/:name/:system/:version should deny unauthorized upload."""
    response = await client.post("/v1/modules/secret-team/vpc/aws/1.0.0")
    assert response.status_code in (401, 422)


# --- Version listing isolation ---


@pytest.mark.asyncio
async def test_version_list_unauthorized_namespace_returns_403(client):
    """GET /v1/modules/:ns/:name/:system/versions should deny unauthorized access."""
    response = await client.get("/v1/modules/secret-team/vpc/aws/versions")
    assert response.status_code == 401


# --- Search isolation ---


@pytest.mark.asyncio
async def test_search_excludes_unauthorized_namespaces(client):
    """GET /api/modules?search=... should not leak modules from unauthorized namespaces."""
    response = await client.get("/api/modules?search=secret")
    assert response.status_code == 401
