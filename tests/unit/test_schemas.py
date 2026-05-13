"""Unit tests for Pydantic schema validation."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tsilo.schemas.api_token import TokenCreate, TokenScopeEntry
from tsilo.schemas.metrics import (
    MetricsOverviewData,
    TopModule,
    VersionDownloadInfo,
)
from tsilo.schemas.module import (
    ModuleListItem,
    ModuleListResponse,
    ModuleVersionSummary,
    PaginationInfo,
    VersionInput,
)
from tsilo.schemas.namespace import NamespaceCreate, PermissionCreate
from tsilo.schemas.oauth import AuthorizationRequest, OAuthError, TokenRequest, TokenResponse
from tsilo.schemas.terraform import (
    ServiceDiscoveryResponse,
    VersionEntry,
    VersionsResponse,
)

# ── Terraform Protocol Schemas ───────────────────────────────────────────────


class TestServiceDiscoveryResponse:
    def test_default_values(self):
        resp = ServiceDiscoveryResponse()
        data = resp.model_dump(by_alias=True)
        assert data["modules.v1"] == "/v1/modules/"
        assert data["login.v1"]["client"] == "terraform-cli"
        assert data["login.v1"]["ports"] == [10000, 10010]

    def test_serialization_uses_aliases(self):
        resp = ServiceDiscoveryResponse()
        json_str = resp.model_dump_json(by_alias=True)
        assert "modules.v1" in json_str
        assert "login.v1" in json_str


class TestVersionsResponse:
    def test_versions_list(self):
        resp = VersionsResponse(
            modules=[{"versions": [{"version": "1.0.0"}, {"version": "2.0.0"}]}]
        )
        assert len(resp.modules) == 1
        assert resp.modules[0].versions[0].version == "1.0.0"

    def test_empty_versions(self):
        resp = VersionsResponse(modules=[{"versions": []}])
        assert resp.modules[0].versions == []


class TestVersionEntry:
    def test_version_string(self):
        entry = VersionEntry(version="3.2.1")
        assert entry.version == "3.2.1"


# ── Module Schemas ───────────────────────────────────────────────────────────


class TestModuleListItem:
    def test_minimal(self):
        item = ModuleListItem(
            id=uuid.uuid4(),
            namespace="team",
            name="vpc",
            system="aws",
        )
        assert item.description is None
        assert item.version_count == 0
        assert item.total_downloads == 0

    def test_full(self):
        now = datetime.now(tz=UTC)
        item = ModuleListItem(
            id=uuid.uuid4(),
            namespace="team",
            name="vpc",
            system="aws",
            description="A VPC module",
            latest_version="2.0.0",
            version_count=5,
            total_downloads=100,
            last_updated=now,
        )
        assert item.total_downloads == 100


class TestModuleVersionSummary:
    def test_defaults(self):
        vs = ModuleVersionSummary(
            version="1.0.0",
            published_at=datetime.now(tz=UTC),
        )
        assert vs.download_count == 0
        assert vs.deprecated is False
        assert vs.deprecation_reason is None

    def test_deprecated_version(self):
        vs = ModuleVersionSummary(
            version="0.1.0",
            published_at=datetime.now(tz=UTC),
            deprecated=True,
            deprecation_reason="No downloads in 90+ days",
        )
        assert vs.deprecated is True


class TestPaginationInfo:
    def test_pagination(self):
        p = PaginationInfo(page=1, per_page=20, total_pages=5, total_count=100)
        assert p.total_pages == 5


class TestVersionInput:
    def test_defaults(self):
        vi = VersionInput(name="vpc_cidr")
        assert vi.type == "string"
        assert vi.required is True
        assert vi.default is None

    def test_optional_input(self):
        vi = VersionInput(name="tags", type="map(string)", required=False, default="{}")
        assert vi.required is False


class TestModuleListResponse:
    def test_structure(self):
        resp = ModuleListResponse(
            modules=[],
            pagination=PaginationInfo(page=1, per_page=20, total_pages=0, total_count=0),
        )
        assert resp.modules == []


# ── Namespace Schemas ────────────────────────────────────────────────────────


class TestNamespaceCreate:
    def test_valid_name(self):
        ns = NamespaceCreate(name="platform-team")
        assert ns.name == "platform-team"

    def test_name_too_short(self):
        with pytest.raises(ValidationError):
            NamespaceCreate(name="a")

    def test_name_invalid_pattern(self):
        with pytest.raises(ValidationError):
            NamespaceCreate(name="Platform-Team")

    def test_optional_fields(self):
        ns = NamespaceCreate(name="my-team")
        assert ns.display_name is None
        assert ns.description is None

    def test_with_display_name(self):
        ns = NamespaceCreate(name="my-team", display_name="My Team", description="Desc")
        assert ns.display_name == "My Team"


class TestPermissionCreate:
    def test_valid_read(self):
        p = PermissionCreate(group_name="devs", permission_level="read")
        assert p.permission_level == "read"

    def test_valid_write(self):
        p = PermissionCreate(group_name="admins", permission_level="write")
        assert p.permission_level == "write"

    def test_invalid_permission_level(self):
        with pytest.raises(ValidationError):
            PermissionCreate(group_name="devs", permission_level="admin")

    def test_empty_group_name(self):
        with pytest.raises(ValidationError):
            PermissionCreate(group_name="", permission_level="read")


# ── OAuth Schemas ────────────────────────────────────────────────────────────


class TestAuthorizationRequest:
    def test_valid_request(self):
        req = AuthorizationRequest(
            client_id="terraform-cli",
            code_challenge="abc123",
            code_challenge_method="S256",
            redirect_uri="http://localhost:10000/callback",
            response_type="code",
            state="random-state",
        )
        assert req.client_id == "terraform-cli"

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            AuthorizationRequest(
                client_id="terraform-cli",
                # missing code_challenge, etc.
            )


class TestTokenRequest:
    def test_valid_request(self):
        req = TokenRequest(
            grant_type="authorization_code",
            code="auth-code-123",
            redirect_uri="http://localhost:10000/callback",
            client_id="terraform-cli",
            code_verifier="verifier-string",
        )
        assert req.grant_type == "authorization_code"


class TestTokenResponse:
    def test_default_token_type(self):
        resp = TokenResponse(access_token="abc123")
        assert resp.token_type == "Bearer"  # noqa: S105
        assert resp.expires_in is None

    def test_with_expiry(self):
        resp = TokenResponse(access_token="abc123", expires_in=3600)
        assert resp.expires_in == 3600


class TestOAuthError:
    def test_error_response(self):
        err = OAuthError(error="invalid_grant", error_description="Code expired")
        assert err.error == "invalid_grant"


# ── API Token Schemas ────────────────────────────────────────────────────────


class TestTokenScopeEntry:
    def test_valid_read(self):
        scope = TokenScopeEntry(namespace="team", permission="read")
        assert scope.namespace == "team"

    def test_invalid_permission(self):
        with pytest.raises(ValidationError):
            TokenScopeEntry(namespace="team", permission="admin")


class TestTokenCreate:
    def test_valid_create(self):
        tc = TokenCreate(
            name="ci-token",
            scopes=[TokenScopeEntry(namespace="team", permission="read")],
            expires_in_days=30,
        )
        assert tc.name == "ci-token"
        assert len(tc.scopes) == 1

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            TokenCreate(name="x" * 201)

    def test_empty_name(self):
        with pytest.raises(ValidationError):
            TokenCreate(name="")

    def test_expires_in_days_min(self):
        with pytest.raises(ValidationError):
            TokenCreate(name="test", expires_in_days=0)

    def test_expires_in_days_max(self):
        with pytest.raises(ValidationError):
            TokenCreate(name="test", expires_in_days=5000)

    def test_default_no_expiry(self):
        tc = TokenCreate(name="test")
        assert tc.expires_in_days is None


# ── Metrics Schemas ──────────────────────────────────────────────────────────


class TestMetricsOverviewData:
    def test_valid(self):
        data = MetricsOverviewData(
            total_modules=10,
            total_versions=50,
            total_namespaces=3,
            total_downloads=1000,
            downloads_last_30_days=200,
            active_users_last_30_days=15,
            top_modules=[
                TopModule(namespace="team", name="vpc", system="aws", downloads=500),
            ],
            namespace_usage=[],
        )
        assert data.total_modules == 10


class TestVersionDownloadInfo:
    def test_defaults(self):
        vdi = VersionDownloadInfo(version="1.0.0", download_count=42)
        assert vdi.deprecated is False
        assert vdi.last_download_at is None

    def test_deprecated(self):
        vdi = VersionDownloadInfo(
            version="0.1.0",
            download_count=0,
            deprecated=True,
        )
        assert vdi.deprecated is True
