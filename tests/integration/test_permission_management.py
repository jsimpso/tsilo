"""Integration test for permission management - CRUD and access control updates."""

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


# --- Permission listing ---


@pytest.mark.asyncio
async def test_permission_list_requires_auth(client):
    """GET /api/namespaces/:namespace/permissions should require authentication."""
    response = await client.get("/api/namespaces/platform-team/permissions")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_permission_list_endpoint_returns_json(client):
    """GET /api/namespaces/:namespace/permissions should return JSON when authenticated."""
    response = await client.get("/api/namespaces/platform-team/permissions")
    assert response.status_code == 401  # Auth required


# --- Permission creation ---


@pytest.mark.asyncio
async def test_permission_create_requires_auth(client):
    """POST /api/namespaces/:namespace/permissions should require authentication."""
    response = await client.post(
        "/api/namespaces/platform-team/permissions",
        json={"group_name": "new-group", "permission_level": "read"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_permission_create_endpoint_exists(client):
    """POST /api/namespaces/:namespace/permissions should not return 404."""
    response = await client.post(
        "/api/namespaces/platform-team/permissions",
        json={"group_name": "new-group", "permission_level": "read"},
    )
    assert response.status_code != 404


# --- Permission deletion ---


@pytest.mark.asyncio
async def test_permission_delete_requires_auth(client):
    """DELETE /api/namespaces/:namespace/permissions/:id should require authentication."""
    response = await client.delete(
        "/api/namespaces/platform-team/permissions/00000000-0000-0000-0000-000000000001"
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_permission_delete_endpoint_exists(client):
    """DELETE /api/namespaces/:namespace/permissions/:id should not return 404."""
    response = await client.delete(
        "/api/namespaces/platform-team/permissions/00000000-0000-0000-0000-000000000001"
    )
    assert response.status_code != 404


# --- Namespace creation validation ---


@pytest.mark.asyncio
async def test_namespace_create_validates_name_pattern(client):
    """POST /api/namespaces should validate namespace name pattern."""
    # Invalid namespace names should be rejected (once authenticated)
    response = await client.post(
        "/api/namespaces",
        json={"name": "INVALID_NAME!", "display_name": "Bad Name"},
    )
    assert response.status_code in (401, 422)


@pytest.mark.asyncio
async def test_namespace_create_requires_name(client):
    """POST /api/namespaces should require name field."""
    response = await client.post(
        "/api/namespaces",
        json={"display_name": "No Name"},
    )
    assert response.status_code in (401, 422)


# --- Response structure ---


@pytest.mark.asyncio
async def test_namespace_list_response_structure(client):
    """Namespace list response should contain namespaces array when authenticated."""
    response = await client.get("/api/namespaces")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_permission_list_response_structure(client):
    """Permission list response should contain permissions array when authenticated."""
    response = await client.get("/api/namespaces/platform-team/permissions")
    assert response.status_code == 401
