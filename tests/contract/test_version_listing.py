"""Contract test for version listing - verify versions returned correctly."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tsilo.main import app
from tsilo.middleware.auth import CurrentUser, get_current_user
from tsilo.models.user import User


def _make_user(groups: list[str] | None = None) -> CurrentUser:
    """Create a mock authenticated user."""
    user = User(
        id=uuid.uuid4(),
        oidc_sub="test|123",
        email="test@example.com",
        name="Test User",
        groups=groups or ["platform-team-developers"],
        last_login_at=datetime.now(tz=timezone.utc),
    )
    return CurrentUser(user=user, auth_method="api_token")


@pytest.fixture
async def client():
    """Create an async test client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_auth():
    """Override authentication dependency to return a test user."""
    user = _make_user()

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_db():
    """Mock database session dependency."""
    from tsilo.models import get_db

    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session
    yield mock_session
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_version_listing_requires_authentication(client):
    """Version listing must require authentication (401 without token)."""
    from tsilo.models import get_db

    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        response = await client.get("/v1/modules/platform-team/vpc/aws/versions")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_version_listing_returns_versions_structure(client, mock_auth, mock_db):
    """Version listing must return {modules: [{versions: [...]}]} structure."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.list_versions.return_value = ["2.0.0", "1.2.3", "1.0.0"]
            mock_ver_cls.return_value = mock_ver

            response = await client.get("/v1/modules/platform-team/vpc/aws/versions")
            assert response.status_code == 200
            data = response.json()
            assert "modules" in data
            assert len(data["modules"]) == 1
            assert "versions" in data["modules"][0]


@pytest.mark.asyncio
async def test_version_listing_descending_order(client, mock_auth, mock_db):
    """Versions must be returned in descending semantic version order."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.list_versions.return_value = ["2.0.0", "1.2.3", "1.0.0"]
            mock_ver_cls.return_value = mock_ver

            response = await client.get("/v1/modules/platform-team/vpc/aws/versions")
            data = response.json()
            versions = [v["version"] for v in data["modules"][0]["versions"]]
            assert versions == ["2.0.0", "1.2.3", "1.0.0"]


@pytest.mark.asyncio
async def test_version_listing_forbidden_without_namespace_access(client, mock_auth, mock_db):
    """Version listing must return 403 if user lacks read access to namespace."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = False
        mock_perm_cls.return_value = mock_perm

        response = await client.get("/v1/modules/secret-team/vpc/aws/versions")
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_version_listing_not_found_for_nonexistent_module(client, mock_auth, mock_db):
    """Version listing must return 404 if module does not exist."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.list_versions.return_value = None  # Module not found
            mock_ver_cls.return_value = mock_ver

            response = await client.get("/v1/modules/platform-team/nonexistent/aws/versions")
            assert response.status_code == 404
