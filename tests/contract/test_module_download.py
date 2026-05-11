"""Contract test for module download - verify download URL generation and auth."""

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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False) as ac:
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
async def test_module_download_requires_authentication(client):
    """Module download must require authentication (401 without token)."""
    from tsilo.models import get_db

    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        response = await client.get("/v1/modules/platform-team/vpc/aws/1.2.3/download")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_module_download_returns_x_terraform_get_header(client, mock_auth, mock_db):
    """Module download must return 204 with X-Terraform-Get header containing pre-signed URL."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.get_version.return_value = {
                "version": "1.2.3",
                "module_id": uuid.uuid4(),
                "version_id": uuid.uuid4(),
            }
            mock_ver_cls.return_value = mock_ver

            with patch("tsilo.api.registry.StorageService") as mock_storage_cls:
                mock_storage = mock_storage_cls.return_value
                mock_storage.generate_download_url.return_value = (
                    "https://s3.example.com/platform-team/vpc/aws/1.2.3/module.tar.gz?signed=1"
                )

                with patch("tsilo.api.registry.MetricsService") as mock_metrics_cls:
                    mock_metrics = AsyncMock()
                    mock_metrics_cls.return_value = mock_metrics

                    response = await client.get("/v1/modules/platform-team/vpc/aws/1.2.3/download")
                    assert response.status_code == 204
                    assert "x-terraform-get" in response.headers
                    assert "s3.example.com" in response.headers["x-terraform-get"]


@pytest.mark.asyncio
async def test_module_download_increments_counter(client, mock_auth, mock_db):
    """Module download must increment the download counter."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.get_version.return_value = {
                "version": "1.2.3",
                "module_id": uuid.uuid4(),
                "version_id": uuid.uuid4(),
            }
            mock_ver_cls.return_value = mock_ver

            with patch("tsilo.api.registry.StorageService") as mock_storage_cls:
                mock_storage = mock_storage_cls.return_value
                mock_storage.generate_download_url.return_value = "https://s3.example.com/url"

                with patch("tsilo.api.registry.MetricsService") as mock_metrics_cls:
                    mock_metrics = AsyncMock()
                    mock_metrics_cls.return_value = mock_metrics

                    await client.get("/v1/modules/platform-team/vpc/aws/1.2.3/download")
                    mock_metrics.increment_download_count.assert_called_once()


@pytest.mark.asyncio
async def test_module_download_forbidden_without_namespace_access(client, mock_auth, mock_db):
    """Module download must return 403 if user lacks read access."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = False
        mock_perm_cls.return_value = mock_perm

        response = await client.get("/v1/modules/secret-team/vpc/aws/1.2.3/download")
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_module_download_not_found_for_nonexistent_version(client, mock_auth, mock_db):
    """Module download must return 404 if version does not exist."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.get_version.return_value = None  # Version not found
            mock_ver_cls.return_value = mock_ver

            response = await client.get("/v1/modules/platform-team/vpc/aws/9.9.9/download")
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_module_download_no_cache(client, mock_auth, mock_db):
    """Module download must not be cached (each download must be tracked)."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.get_version.return_value = {
                "version": "1.2.3",
                "module_id": uuid.uuid4(),
                "version_id": uuid.uuid4(),
            }
            mock_ver_cls.return_value = mock_ver

            with patch("tsilo.api.registry.StorageService") as mock_storage_cls:
                mock_storage = mock_storage_cls.return_value
                mock_storage.generate_download_url.return_value = "https://s3.example.com/url"

                with patch("tsilo.api.registry.MetricsService") as mock_metrics_cls:
                    mock_metrics = AsyncMock()
                    mock_metrics_cls.return_value = mock_metrics

                    response = await client.get("/v1/modules/platform-team/vpc/aws/1.2.3/download")
                    cache_control = response.headers.get("cache-control", "")
                    assert "no-store" in cache_control
