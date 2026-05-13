"""Unit tests for service-layer business logic (module parser, semver, version service, cache)."""

import io
import tarfile
import time

import pytest

from tsilo.services.cache import TTLCache
from tsilo.services.module_parser import ModuleParser, ParseError
from tsilo.services.version_service import VersionService, _semver_compare


# ── TTL Cache ────────────────────────────────────────────────────────────────


class TestTTLCache:
    def test_get_set(self):
        cache = TTLCache(default_ttl=60.0)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_get_missing_key(self):
        cache = TTLCache(default_ttl=60.0)
        assert cache.get("missing") is None

    def test_expired_entry(self):
        cache = TTLCache(default_ttl=0.01)
        cache.set("key", "value")
        time.sleep(0.02)
        assert cache.get("key") is None

    def test_invalidate(self):
        cache = TTLCache(default_ttl=60.0)
        cache.set("key", "value")
        cache.invalidate("key")
        assert cache.get("key") is None

    def test_clear(self):
        cache = TTLCache(default_ttl=60.0)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_max_size_eviction(self):
        cache = TTLCache(default_ttl=60.0, max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # evicts "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_custom_ttl(self):
        cache = TTLCache(default_ttl=60.0)
        cache.set("short", "val", ttl=0.01)
        time.sleep(0.02)
        assert cache.get("short") is None

    def test_boolean_false_cached(self):
        cache = TTLCache(default_ttl=60.0)
        cache.set("perm", False)
        assert cache.get("perm") is False

# ── Semver Comparison ────────────────────────────────────────────────────────


class TestSemverCompare:
    def test_equal_versions(self):
        assert _semver_compare("1.0.0", "1.0.0") == 0

    def test_major_greater(self):
        assert _semver_compare("2.0.0", "1.0.0") > 0

    def test_major_less(self):
        assert _semver_compare("1.0.0", "2.0.0") < 0

    def test_minor_greater(self):
        assert _semver_compare("1.2.0", "1.1.0") > 0

    def test_patch_greater(self):
        assert _semver_compare("1.0.2", "1.0.1") > 0

    def test_prerelease_less_than_release(self):
        assert _semver_compare("1.0.0-alpha", "1.0.0") < 0

    def test_release_greater_than_prerelease(self):
        assert _semver_compare("1.0.0", "1.0.0-beta") > 0

    def test_prerelease_ordering(self):
        assert _semver_compare("1.0.0-alpha", "1.0.0-beta") < 0

    def test_equal_prerelease(self):
        assert _semver_compare("1.0.0-rc.1", "1.0.0-rc.1") == 0

    def test_sorting_descending(self):
        versions = ["1.0.0", "2.1.0", "1.0.1", "2.0.0", "0.9.0"]
        from functools import cmp_to_key

        sorted_desc = sorted(versions, key=cmp_to_key(_semver_compare), reverse=True)
        assert sorted_desc == ["2.1.0", "2.0.0", "1.0.1", "1.0.0", "0.9.0"]


# ── Semver Validation ────────────────────────────────────────────────────────


class TestValidateSemver:
    def test_valid_versions(self):
        for v in ("0.0.1", "1.0.0", "10.20.30", "1.0.0-alpha", "1.0.0+build"):
            assert VersionService.validate_semver(v) is True, f"{v} should be valid"

    def test_invalid_versions(self):
        for v in ("1.0", "v1.0.0", "01.0.0", "latest", "1.0.0.0", ""):
            assert VersionService.validate_semver(v) is False, f"{v} should be invalid"


# ── Module Parser Helpers ────────────────────────────────────────────────────


def _make_tar_gz(files: dict[str, str]) -> bytes:
    """Create an in-memory .tar.gz archive from a dict of {path: content}."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return buf.read()


# ── Module Parser Tests ──────────────────────────────────────────────────────


class TestModuleParser:
    def setup_method(self):
        self.parser = ModuleParser()

    def test_parse_simple_module(self):
        archive = _make_tar_gz(
            {
                "module/main.tf": 'resource "null_resource" "test" {}',
                "module/variables.tf": """
variable "name" {
  type        = string
  description = "The name"
}

variable "count" {
  type        = number
  description = "Number of instances"
  default     = 1
}
""",
                "module/outputs.tf": """
output "id" {
  description = "The resource ID"
}
""",
                "module/README.md": "# My Module\n\nA test module.",
            }
        )

        result = self.parser.parse(archive)

        assert len(result["inputs"]) == 2
        assert result["inputs"][0]["name"] == "name"
        assert result["inputs"][0]["type"] == "string"
        assert result["inputs"][0]["required"] is True
        assert result["inputs"][1]["name"] == "count"
        assert result["inputs"][1]["required"] is False
        assert result["inputs"][1]["default"] == "1"

        assert len(result["outputs"]) == 1
        assert result["outputs"][0]["name"] == "id"
        assert result["outputs"][0]["description"] == "The resource ID"

        assert result["readme"] == "# My Module\n\nA test module."

    def test_parse_no_tf_files_raises(self):
        archive = _make_tar_gz(
            {
                "module/README.md": "# Just a readme",
            }
        )
        with pytest.raises(ParseError, match="at least one .tf file"):
            self.parser.parse(archive)

    def test_parse_invalid_archive(self):
        with pytest.raises(ParseError, match="Invalid .tar.gz"):
            self.parser.parse(b"not a tar.gz file")

    def test_parse_empty_tf_file(self):
        archive = _make_tar_gz(
            {
                "module/main.tf": "",
            }
        )
        result = self.parser.parse(archive)
        assert result["inputs"] == []
        assert result["outputs"] == []
        assert result["readme"] is None

    def test_parse_no_readme(self):
        archive = _make_tar_gz(
            {
                "module/main.tf": 'resource "null_resource" "test" {}',
            }
        )
        result = self.parser.parse(archive)
        assert result["readme"] is None

    def test_parse_deduplicates_variables(self):
        archive = _make_tar_gz(
            {
                "module/main.tf": """
variable "name" {
  type = string
  description = "First"
}
""",
                "module/variables.tf": """
variable "name" {
  type = string
  description = "Second"
}
""",
            }
        )
        result = self.parser.parse(archive)
        # Should keep the first occurrence
        assert len(result["inputs"]) == 1

    def test_parse_skips_path_traversal(self):
        """Verify that archive members with path traversal are skipped."""
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            # Legitimate file
            data = b'resource "null_resource" "ok" {}'
            info = tarfile.TarInfo(name="module/main.tf")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

            # Path traversal file (should be skipped)
            evil_data = b'variable "evil" { type = string }'
            evil_info = tarfile.TarInfo(name="../etc/evil.tf")
            evil_info.size = len(evil_data)
            tar.addfile(evil_info, io.BytesIO(evil_data))

        buf.seek(0)
        result = self.parser.parse(buf.read())

        # Only the legitimate file's content should be parsed
        evil_names = [i["name"] for i in result["inputs"]]
        assert "evil" not in evil_names

    def test_parse_variable_without_description(self):
        archive = _make_tar_gz(
            {
                "module/variables.tf": """
variable "simple" {
  type = string
}
""",
            }
        )
        result = self.parser.parse(archive)
        assert len(result["inputs"]) == 1
        assert result["inputs"][0]["description"] is None

    def test_parse_output_without_description(self):
        archive = _make_tar_gz(
            {
                "module/outputs.tf": """
output "bare" {
  value = "hello"
}
""",
            }
        )
        result = self.parser.parse(archive)
        assert len(result["outputs"]) == 1
        assert result["outputs"][0]["description"] is None
