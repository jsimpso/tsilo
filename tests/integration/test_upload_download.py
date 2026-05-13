"""Integration test for upload-download cycle - upload module, verify S3 storage,
then download via Terraform registry protocol."""

import io
import tarfile
import uuid
from datetime import UTC, datetime
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
        email="author@example.com",
        name="Module Author",
        groups=groups or ["platform-team-developers"],
        last_login_at=datetime.now(tz=UTC),
    )
    return CurrentUser(user=user, auth_method="api_token")


def _make_tar_gz() -> bytes:
    """Create a valid module .tar.gz archive."""
    files = {
        "main.tf": 'resource "null_resource" "example" {}',
        "variables.tf": ('variable "name" {\n  type = string\n  description = "The name"\n}'),
        "outputs.tf": (
            'output "id" {\n  value = null_resource.example.id\n  description = "The ID"\n}'
        ),
        "README.md": "# Test Module\n\nA test module for integration testing.",
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
async def test_upload_then_download_cycle(client, mock_auth, mock_db):
    """End-to-end test: upload a module, then download it via Terraform protocol.

    1. Upload module via POST /v1/modules/:namespace/:name/:provider/:version
    2. List versions via GET /v1/modules/:namespace/:name/:provider/versions
    3. Download via GET /v1/modules/:namespace/:name/:provider/:version/download
    """
    version_id = uuid.uuid4()
    module_id = uuid.uuid4()
    ns = "platform-team"
    name = "vpc"
    provider = "aws"
    version = "1.0.0"

    # Step 1: Upload module
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_write_access.return_value = True
        mock_perm.check_read_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.check_version_exists.return_value = False
            mock_ver.create_version.return_value = {
                "id": version_id,
                "module_id": module_id,
                "namespace": ns,
                "name": name,
                "provider": provider,
                "version": version,
                "inputs": [
                    {"name": "name", "type": "string", "description": "The name", "required": True}
                ],
                "outputs": [{"name": "id", "description": "The ID"}],
                "package_url": f"s3://tsilo-modules/{ns}/{name}/{provider}/{version}/module.tar.gz",
                "package_size_bytes": 1024,
                "checksum_sha256": "a" * 64,
                "published_at": datetime.now(tz=UTC).isoformat(),
            }
            mock_ver_cls.return_value = mock_ver

            tar_data = _make_tar_gz()
            upload_response = await client.post(
                f"/v1/modules/{ns}/{name}/{provider}/{version}",
                files={"file": ("module.tar.gz", tar_data, "application/gzip")},
            )
            assert upload_response.status_code == 201
            upload_data = upload_response.json()
            assert upload_data["version"] == version
            assert upload_data["namespace"] == ns

    # Step 2: List versions (simulating Terraform CLI version resolution)
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.list_versions.return_value = [version]
            mock_ver_cls.return_value = mock_ver

            versions_response = await client.get(f"/v1/modules/{ns}/{name}/{provider}/versions")
            assert versions_response.status_code == 200
            versions_data = versions_response.json()
            available = [v["version"] for v in versions_data["modules"][0]["versions"]]
            assert version in available

    # Step 3: Download module (simulating Terraform CLI download)
    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_read_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.get_version.return_value = {
                "version": version,
                "module_id": module_id,
                "version_id": version_id,
            }
            mock_ver_cls.return_value = mock_ver

            with patch("tsilo.api.registry.StorageService") as mock_storage_cls:
                download_url = f"https://s3.example.com/{ns}/{name}/{provider}/{version}/module.tar.gz?signed=1"
                mock_storage_cls.return_value.generate_download_url.return_value = download_url

                with patch("tsilo.api.registry.MetricsService") as mock_metrics_cls:
                    mock_metrics_cls.return_value = AsyncMock()

                    dl_response = await client.get(
                        f"/v1/modules/{ns}/{name}/{provider}/{version}/download"
                    )
                    assert dl_response.status_code == 204
                    assert dl_response.headers["x-terraform-get"] == download_url


@pytest.mark.asyncio
async def test_upload_duplicate_then_upload_new_version(client, mock_auth, mock_db):
    """Upload v1.0.0, attempt duplicate (409), then upload v1.1.0 successfully."""
    ns = "platform-team"
    name = "vpc"
    provider = "aws"

    with patch("tsilo.api.registry.PermissionService") as mock_perm_cls:
        mock_perm = AsyncMock()
        mock_perm.check_write_access.return_value = True
        mock_perm_cls.return_value = mock_perm

        # Attempt duplicate upload of v1.0.0
        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.check_version_exists.return_value = True
            mock_ver_cls.return_value = mock_ver

            tar_data = _make_tar_gz()
            dup_response = await client.post(
                f"/v1/modules/{ns}/{name}/{provider}/1.0.0",
                files={"file": ("module.tar.gz", tar_data, "application/gzip")},
            )
            assert dup_response.status_code == 409

        # Upload v1.1.0 successfully
        with patch("tsilo.api.registry.VersionService") as mock_ver_cls:
            mock_ver = AsyncMock()
            mock_ver.check_version_exists.return_value = False
            mock_ver.create_version.return_value = {
                "id": uuid.uuid4(),
                "module_id": uuid.uuid4(),
                "namespace": ns,
                "name": name,
                "provider": provider,
                "version": "1.1.0",
                "inputs": [],
                "outputs": [],
                "package_url": f"s3://tsilo-modules/{ns}/{name}/{provider}/1.1.0/module.tar.gz",
                "package_size_bytes": 1024,
                "checksum_sha256": "b" * 64,
                "published_at": datetime.now(tz=UTC).isoformat(),
            }
            mock_ver_cls.return_value = mock_ver

            tar_data = _make_tar_gz()
            new_response = await client.post(
                f"/v1/modules/{ns}/{name}/{provider}/1.1.0",
                files={"file": ("module.tar.gz", tar_data, "application/gzip")},
            )
            assert new_response.status_code == 201
            assert new_response.json()["version"] == "1.1.0"
