"""Contract test for module upload - verify multipart upload, version validation,
duplicate rejection, and permission enforcement."""

import io
import tarfile
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_tar_gz(files: dict[str, str] | None = None) -> bytes:
    """Create a valid .tar.gz archive with the given files.

    Args:
        files: dict mapping filename to content string. Defaults to a minimal module.
    """
    if files is None:
        files = {
            "main.tf": 'resource "null_resource" "example" {}',
            "variables.tf": 'variable "name" {\n  type = string\n  description = "The name"\n}',
            "outputs.tf": 'output "id" {\n  value = null_resource.example.id\n  description = "The ID"\n}',
            "README.md": "# Test Module\n\nA test module.",
        }
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


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


# --- Authentication tests ---


@pytest.mark.asyncio
async def test_upload_requires_authentication(client):
    """Module upload must require authentication (401 without token)."""
    from tsilo.models import get_db

    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        tar_data = _make_tar_gz()
        response = await client.post(
            "/v1/modules/platform-team/vpc/aws/1.0.0",
            files={"file": ("module.tar.gz", tar_data, "application/gzip")},
        )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


# --- Permission tests ---


@pytest.mark.asyncio
async def test_upload_requires_write_permission(client, mock_auth, mock_db):
    """Module upload must require write permission on the namespace (403 without)."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_write_access.return_value = False
        mock_perm_cls.return_value = mock_perm

        tar_data = _make_tar_gz()
        response = await client.post(
            "/v1/modules/platform-team/vpc/aws/1.0.0",
            files={"file": ("module.tar.gz", tar_data, "application/gzip")},
        )
        assert response.status_code == 403
        data = response.json()
        assert "errors" in data
        assert data["errors"][0]["status"] == "403"


# --- Version validation tests ---


@pytest.mark.asyncio
async def test_upload_rejects_invalid_semver(client, mock_auth, mock_db):
    """Module upload must reject invalid semantic version format."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_write_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        tar_data = _make_tar_gz()
        response = await client.post(
            "/v1/modules/platform-team/vpc/aws/1.0",
            files={"file": ("module.tar.gz", tar_data, "application/gzip")},
        )
        assert response.status_code == 400
        data = response.json()
        assert "errors" in data
        assert "semantic version" in data["errors"][0]["detail"].lower()


# --- Duplicate rejection tests ---


@pytest.mark.asyncio
async def test_upload_rejects_duplicate_version(client, mock_auth, mock_db):
    """Module upload must reject duplicate version (409 Conflict)."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_write_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.check_version_exists.return_value = True
            mock_ver_cls.return_value = mock_ver

            tar_data = _make_tar_gz()
            response = await client.post(
                "/v1/modules/platform-team/vpc/aws/1.0.0",
                files={"file": ("module.tar.gz", tar_data, "application/gzip")},
            )
            assert response.status_code == 409
            data = response.json()
            assert data["errors"][0]["status"] == "409"


# --- Successful upload tests ---


@pytest.mark.asyncio
async def test_upload_success_returns_201(client, mock_auth, mock_db):
    """Successful module upload must return 201 Created with module version details."""
    version_id = uuid.uuid4()
    module_id = uuid.uuid4()

    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_write_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.check_version_exists.return_value = False
            mock_ver.create_version.return_value = {
                "id": version_id,
                "module_id": module_id,
                "namespace": "platform-team",
                "name": "vpc",
                "provider": "aws",
                "version": "1.0.0",
                "inputs": [{"name": "name", "type": "string", "description": "The name", "required": True}],
                "outputs": [{"name": "id", "description": "The ID"}],
                "package_url": "s3://tsilo-modules/platform-team/vpc/aws/1.0.0/module.tar.gz",
                "package_size_bytes": 1024,
                "checksum_sha256": "a" * 64,
                "published_at": datetime.now(tz=timezone.utc).isoformat(),
            }
            mock_ver_cls.return_value = mock_ver

            tar_data = _make_tar_gz()
            response = await client.post(
                "/v1/modules/platform-team/vpc/aws/1.0.0",
                files={"file": ("module.tar.gz", tar_data, "application/gzip")},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["namespace"] == "platform-team"
            assert data["name"] == "vpc"
            assert data["provider"] == "aws"
            assert data["version"] == "1.0.0"
            assert "inputs" in data
            assert "outputs" in data
            assert "checksum_sha256" in data


# --- Package validation tests ---


@pytest.mark.asyncio
async def test_upload_rejects_non_gzip(client, mock_auth, mock_db):
    """Module upload must reject non-gzip files."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_write_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.check_version_exists.return_value = False
            mock_ver_cls.return_value = mock_ver

            response = await client.post(
                "/v1/modules/platform-team/vpc/aws/1.0.0",
                files={"file": ("module.tar.gz", b"not a tar gz file", "application/gzip")},
            )
            assert response.status_code == 400
            data = response.json()
            assert "errors" in data


@pytest.mark.asyncio
async def test_upload_rejects_tar_without_tf_files(client, mock_auth, mock_db):
    """Module upload must reject packages without .tf files."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_write_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.check_version_exists.return_value = False
            mock_ver_cls.return_value = mock_ver

            tar_data = _make_tar_gz({"README.md": "# Just a readme"})
            response = await client.post(
                "/v1/modules/platform-team/vpc/aws/1.0.0",
                files={"file": ("module.tar.gz", tar_data, "application/gzip")},
            )
            assert response.status_code == 400
            data = response.json()
            assert ".tf" in data["errors"][0]["detail"].lower() or "terraform" in data["errors"][0]["detail"].lower()


# --- Size limit tests ---


@pytest.mark.asyncio
async def test_upload_rejects_oversized_package(client, mock_auth, mock_db):
    """Module upload must reject packages exceeding size limit (413)."""
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_write_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.check_version_exists.return_value = False
            mock_ver_cls.return_value = mock_ver

            # Patch the max upload size to a small value for testing
            with patch("tsilo.api.registry.MAX_UPLOAD_SIZE_BYTES", 100):
                tar_data = _make_tar_gz()
                response = await client.post(
                    "/v1/modules/platform-team/vpc/aws/1.0.0",
                    files={"file": ("module.tar.gz", tar_data, "application/gzip")},
                )
                assert response.status_code == 413
                data = response.json()
                assert data["errors"][0]["status"] == "413"
