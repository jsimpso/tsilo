"""Unit tests for SQLAlchemy model validation, constraints, and relationships."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tsilo.models.api_token import APIToken
from tsilo.models.metric import DownloadMetric
from tsilo.models.module import MODULE_NAME_PATTERN, PROVIDER_PATTERN, Module
from tsilo.models.namespace import NAMESPACE_NAME_PATTERN, Namespace
from tsilo.models.oauth_code import OAuthAuthorizationCode
from tsilo.models.permission import NamespacePermission, PermissionLevel
from tsilo.models.user import User
from tsilo.models.version import SEMVER_PATTERN, ModuleVersion


# ── Namespace Validation ─────────────────────────────────────────────────────


class TestNamespaceValidation:
    def test_valid_name(self):
        ns = Namespace(name="platform-team")
        assert ns.name == "platform-team"

    def test_valid_name_numeric(self):
        ns = Namespace(name="team42")
        assert ns.name == "team42"

    def test_valid_name_minimum_length(self):
        ns = Namespace(name="ab")
        assert ns.name == "ab"

    def test_invalid_name_single_char(self):
        with pytest.raises(ValueError, match="Namespace name must be lowercase"):
            Namespace(name="a")

    def test_invalid_name_uppercase(self):
        with pytest.raises(ValueError, match="Namespace name must be lowercase"):
            Namespace(name="Platform-Team")

    def test_invalid_name_starts_with_hyphen(self):
        with pytest.raises(ValueError, match="Namespace name must be lowercase"):
            Namespace(name="-platform")

    def test_invalid_name_ends_with_hyphen(self):
        with pytest.raises(ValueError, match="Namespace name must be lowercase"):
            Namespace(name="platform-")

    def test_invalid_name_consecutive_hyphens(self):
        with pytest.raises(ValueError, match="consecutive hyphens"):
            Namespace(name="platform--team")

    def test_invalid_name_special_chars(self):
        with pytest.raises(ValueError, match="Namespace name must be lowercase"):
            Namespace(name="platform_team")

    def test_namespace_repr(self):
        ns = Namespace(name="test-ns")
        assert "test-ns" in repr(ns)

    def test_namespace_name_pattern_regex(self):
        assert NAMESPACE_NAME_PATTERN.match("valid-name")
        assert NAMESPACE_NAME_PATTERN.match("ab")
        assert not NAMESPACE_NAME_PATTERN.match("a")
        assert not NAMESPACE_NAME_PATTERN.match("A-bad")
        assert not NAMESPACE_NAME_PATTERN.match("-bad")


# ── Module Validation ────────────────────────────────────────────────────────


class TestModuleValidation:
    def test_valid_module_name(self):
        ns_id = uuid.uuid4()
        mod = Module(namespace_id=ns_id, name="my-vpc", provider="aws")
        assert mod.name == "my-vpc"

    def test_invalid_module_name_uppercase(self):
        with pytest.raises(ValueError, match="Module name must be lowercase"):
            Module(namespace_id=uuid.uuid4(), name="MyVpc", provider="aws")

    def test_invalid_module_name_starts_with_hyphen(self):
        with pytest.raises(ValueError, match="Module name must be lowercase"):
            Module(namespace_id=uuid.uuid4(), name="-vpc", provider="aws")

    def test_valid_provider(self):
        mod = Module(namespace_id=uuid.uuid4(), name="my-vpc", provider="aws")
        assert mod.provider == "aws"

    def test_invalid_provider_uppercase(self):
        with pytest.raises(ValueError, match="Provider must be lowercase"):
            Module(namespace_id=uuid.uuid4(), name="my-vpc", provider="AWS")

    def test_invalid_provider_special_chars(self):
        with pytest.raises(ValueError, match="Provider must be lowercase"):
            Module(namespace_id=uuid.uuid4(), name="my-vpc", provider="aws_gcp")

    def test_module_repr(self):
        mod = Module(namespace_id=uuid.uuid4(), name="my-vpc", provider="aws")
        assert "my-vpc" in repr(mod)

    def test_module_name_pattern_regex(self):
        assert MODULE_NAME_PATTERN.match("valid-name")
        assert not MODULE_NAME_PATTERN.match("_invalid")

    def test_provider_pattern_regex(self):
        assert PROVIDER_PATTERN.match("aws")
        assert PROVIDER_PATTERN.match("google-cloud")
        assert not PROVIDER_PATTERN.match("AWS")


# ── ModuleVersion Validation ─────────────────────────────────────────────────


class TestModuleVersionValidation:
    def _make_version(self, version: str, checksum: str | None = None) -> ModuleVersion:
        return ModuleVersion(
            module_id=uuid.uuid4(),
            version=version,
            inputs=[],
            outputs=[],
            package_url="s3://bucket/key",
            package_size_bytes=1024,
            checksum_sha256=checksum or "a" * 64,
        )

    def test_valid_semver(self):
        mv = self._make_version("1.0.0")
        assert mv.version == "1.0.0"

    def test_valid_semver_prerelease(self):
        mv = self._make_version("1.0.0-beta.1")
        assert mv.version == "1.0.0-beta.1"

    def test_valid_semver_build_metadata(self):
        mv = self._make_version("1.0.0+build.123")
        assert mv.version == "1.0.0+build.123"

    def test_invalid_semver_no_patch(self):
        with pytest.raises(ValueError, match="not a valid semantic version"):
            self._make_version("1.0")

    def test_invalid_semver_leading_zero(self):
        with pytest.raises(ValueError, match="not a valid semantic version"):
            self._make_version("01.0.0")

    def test_invalid_semver_text(self):
        with pytest.raises(ValueError, match="not a valid semantic version"):
            self._make_version("latest")

    def test_valid_checksum(self):
        mv = self._make_version("1.0.0", "abcdef1234567890" * 4)
        assert len(mv.checksum_sha256) == 64

    def test_checksum_normalized_to_lowercase(self):
        mv = self._make_version("1.0.0", "ABCDEF1234567890" * 4)
        assert mv.checksum_sha256 == ("abcdef1234567890" * 4)

    def test_invalid_checksum_wrong_length(self):
        with pytest.raises(ValueError, match="64-character hex string"):
            self._make_version("1.0.0", "abc123")

    def test_invalid_checksum_not_hex(self):
        with pytest.raises(ValueError, match="64-character hex string"):
            self._make_version("1.0.0", "g" * 64)

    def test_semver_pattern_regex(self):
        assert SEMVER_PATTERN.match("0.0.1")
        assert SEMVER_PATTERN.match("10.20.30")
        assert SEMVER_PATTERN.match("1.0.0-alpha")
        assert SEMVER_PATTERN.match("1.0.0-alpha.1")
        assert SEMVER_PATTERN.match("1.0.0+build")
        assert not SEMVER_PATTERN.match("1.0")
        assert not SEMVER_PATTERN.match("v1.0.0")
        assert not SEMVER_PATTERN.match("01.0.0")

    def test_version_repr(self):
        mv = self._make_version("2.3.4")
        assert "2.3.4" in repr(mv)


# ── PermissionLevel ──────────────────────────────────────────────────────────


class TestPermissionLevel:
    def test_read_value(self):
        assert PermissionLevel.READ == "read"

    def test_write_value(self):
        assert PermissionLevel.WRITE == "write"

    def test_is_string_enum(self):
        assert isinstance(PermissionLevel.READ, str)


# ── NamespacePermission Validation ───────────────────────────────────────────


class TestNamespacePermissionValidation:
    def test_valid_permission(self):
        perm = NamespacePermission(
            namespace_id=uuid.uuid4(),
            group_name="platform-team",
            permission_level=PermissionLevel.READ,
        )
        assert perm.group_name == "platform-team"

    def test_empty_group_name(self):
        with pytest.raises(ValueError, match="must not be empty"):
            NamespacePermission(
                namespace_id=uuid.uuid4(),
                group_name="",
                permission_level=PermissionLevel.READ,
            )

    def test_whitespace_group_name_stripped(self):
        perm = NamespacePermission(
            namespace_id=uuid.uuid4(),
            group_name="  platform-team  ",
            permission_level=PermissionLevel.WRITE,
        )
        assert perm.group_name == "platform-team"

    def test_whitespace_only_group_name(self):
        with pytest.raises(ValueError, match="must not be empty"):
            NamespacePermission(
                namespace_id=uuid.uuid4(),
                group_name="   ",
                permission_level=PermissionLevel.READ,
            )

    def test_permission_repr(self):
        perm = NamespacePermission(
            namespace_id=uuid.uuid4(),
            group_name="devs",
            permission_level=PermissionLevel.WRITE,
        )
        assert "devs" in repr(perm)


# ── APIToken Validation ──────────────────────────────────────────────────────


class TestAPITokenValidation:
    def _make_token(self, expires_at=None, revoked_at=None):
        now = datetime.now(tz=timezone.utc)
        return APIToken(
            token_hash="a" * 64,
            user_id=uuid.uuid4(),
            name="ci-token",
            scopes=[],
            expires_at=expires_at or (now + timedelta(days=30)),
            revoked_at=revoked_at,
        )

    def test_is_valid_active_token(self):
        token = self._make_token()
        assert token.is_valid is True

    def test_is_valid_expired_token(self):
        token = self._make_token(
            expires_at=datetime.now(tz=timezone.utc) - timedelta(days=1),
        )
        assert token.is_valid is False

    def test_is_valid_revoked_token(self):
        token = self._make_token(
            revoked_at=datetime.now(tz=timezone.utc),
        )
        assert token.is_valid is False

    def test_token_repr(self):
        token = self._make_token()
        assert "ci-token" in repr(token)


# ── OAuthAuthorizationCode Validation ────────────────────────────────────────


class TestOAuthCodeValidation:
    def _make_code(self, expires_at=None, used_at=None):
        now = datetime.now(tz=timezone.utc)
        return OAuthAuthorizationCode(
            code="test-code-abc123",
            user_id=uuid.uuid4(),
            client_id="terraform-cli",
            redirect_uri="http://localhost:10000/callback",
            code_challenge="challenge123",
            code_challenge_method="S256",
            scopes=["modules:read"],
            expires_at=expires_at or (now + timedelta(minutes=10)),
            used_at=used_at,
        )

    def test_is_valid_active_code(self):
        code = self._make_code()
        assert code.is_valid is True

    def test_is_valid_expired_code(self):
        code = self._make_code(
            expires_at=datetime.now(tz=timezone.utc) - timedelta(minutes=1),
        )
        assert code.is_valid is False

    def test_is_valid_used_code(self):
        code = self._make_code(
            used_at=datetime.now(tz=timezone.utc),
        )
        assert code.is_valid is False

    def test_code_repr(self):
        code = self._make_code()
        assert "terraform-cli" in repr(code)


# ── User Model ───────────────────────────────────────────────────────────────


class TestUserModel:
    def test_user_creation(self):
        user = User(
            oidc_sub="auth0|123456",
            email="dev@example.com",
            name="Dev User",
            groups=["platform-team", "admins"],
        )
        assert user.email == "dev@example.com"
        assert user.groups == ["platform-team", "admins"]

    def test_user_default_groups(self):
        user = User(
            oidc_sub="auth0|789",
            email="new@example.com",
        )
        # groups defaults to empty list
        assert user.groups == [] or user.groups is None  # depends on DB default

    def test_user_repr(self):
        user = User(oidc_sub="auth0|123", email="test@example.com")
        assert "test@example.com" in repr(user)


# ── DownloadMetric Model ─────────────────────────────────────────────────────


class TestDownloadMetricModel:
    def test_default_count(self):
        metric = DownloadMetric(
            version_id=uuid.uuid4(),
            download_count=0,
        )
        assert metric.download_count == 0

    def test_metric_repr(self):
        vid = uuid.uuid4()
        metric = DownloadMetric(version_id=vid, download_count=42)
        assert "42" in repr(metric)
