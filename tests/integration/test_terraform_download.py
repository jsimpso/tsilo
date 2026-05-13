"""Integration test for Terraform CLI download flow - end-to-end test."""

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
        email="ci@example.com",
        name="CI Pipeline",
        groups=groups or ["platform-team-developers"],
        last_login_at=datetime.now(tz=timezone.utc),
    )
    return CurrentUser(user=user, auth_method="api_token")


@pytest.fixture
async def client():
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as ac:
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
async def test_full_terraform_download_flow(client, mock_auth, mock_db):
    """Simulate complete Terraform CLI download flow:
    1. Service discovery
    2. Version listing
    3. Module download
    """
    # Step 1: Service discovery (no auth)
    response = await client.get("/.well-known/terraform.json")
    assert response.status_code == 200
    discovery = response.json()
    modules_base = discovery["modules.v1"]
    assert modules_base == "/v1/modules/"

    # Step 2: Version listing (auth required)
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.list_versions.return_value = ["2.0.0", "1.2.3", "1.0.0"]
            mock_ver_cls.return_value = mock_ver

            versions_url = f"{modules_base}platform-team/vpc/aws/versions"
            response = await client.get(versions_url)
            assert response.status_code == 200
            versions_data = response.json()
            available_versions = [v["version"] for v in versions_data["modules"][0]["versions"]]
            assert "1.2.3" in available_versions

    # Step 3: Module download (auth required)
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
                download_url = (
                    "https://s3.example.com/platform-team/vpc/aws/1.2.3/module.tar.gz?signed=1"
                )
                mock_storage.generate_download_url.return_value = download_url

                with patch("tsilo.api.registry.MetricsService") as mock_metrics_cls:
                    mock_metrics = AsyncMock()
                    mock_metrics_cls.return_value = mock_metrics

                    download_path = f"{modules_base}platform-team/vpc/aws/1.2.3/download"
                    response = await client.get(download_path)
                    assert response.status_code == 204
                    assert response.headers["x-terraform-get"] == download_url


@pytest.mark.asyncio
async def test_terraform_download_flow_version_constraint(client, mock_auth, mock_db):
    """Simulate Terraform CLI with version constraint (~> 1.0).

    Terraform CLI fetches all versions and picks the best match locally.
    """
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            # Return versions in descending order
            mock_ver.list_versions.return_value = ["2.0.0", "1.5.0", "1.2.3", "1.0.0"]
            mock_ver_cls.return_value = mock_ver

            response = await client.get("/v1/modules/platform-team/vpc/aws/versions")
            assert response.status_code == 200
            versions = [v["version"] for v in response.json()["modules"][0]["versions"]]

            # Terraform CLI would pick 1.5.0 for ~> 1.0 constraint (highest 1.x)
            # Verify all versions available for client-side selection
            assert "2.0.0" in versions
            assert "1.5.0" in versions
            assert "1.2.3" in versions
            assert "1.0.0" in versions


@pytest.mark.asyncio
async def test_terraform_download_flow_missing_module(client, mock_auth, mock_db):
    """Terraform CLI gets 404 for non-existent module."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.list_versions.return_value = None
            mock_ver_cls.return_value = mock_ver

            response = await client.get("/v1/modules/platform-team/nonexistent/aws/versions")
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_terraform_download_flow_no_permissions(client, mock_auth, mock_db):
    """Terraform CLI gets 403 for unauthorized namespace."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = False
        mock_perm_cls.return_value = mock_perm

        response = await client.get("/v1/modules/secret-team/vpc/aws/versions")
        assert response.status_code == 403
