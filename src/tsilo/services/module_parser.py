"""Terraform module parser - extract inputs, outputs, and README from module packages."""

import io
import re
import tarfile
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# HCL variable block pattern: variable "name" { ... }
_VARIABLE_BLOCK_RE = re.compile(
    r'variable\s+"([^"]+)"\s*\{([^}]*)\}',
    re.DOTALL,
)

# HCL output block pattern: output "name" { ... }
_OUTPUT_BLOCK_RE = re.compile(
    r'output\s+"([^"]+)"\s*\{([^}]*)\}',
    re.DOTALL,
)

# Attribute patterns within blocks
_TYPE_RE = re.compile(r"^\s*type\s*=\s*(.+)", re.MULTILINE)
_DESC_RE = re.compile(r'^\s*description\s*=\s*"((?:[^"\\]|\\.)*)"', re.MULTILINE)
_DEFAULT_RE = re.compile(r"^\s*default\s*=\s*(.+)", re.MULTILINE)

# Maximum size for individual extracted files (10 MB)
_MAX_FILE_SIZE = 10 * 1024 * 1024


class ParseError(Exception):
    """Raised when module package parsing fails."""

    pass


class ModuleParser:
    """Parses a Terraform module .tar.gz package to extract metadata."""

    def parse(self, file_data: bytes) -> dict[str, Any]:
        """Parse a .tar.gz module package.

        Returns a dict with keys: inputs, outputs, readme, tf_files.
        Raises ParseError if the archive is invalid or contains no .tf files.
        """
        try:
            with tarfile.open(fileobj=io.BytesIO(file_data), mode="r:gz") as tar_file:
                return self._extract_metadata(tar_file)
        except (tarfile.TarError, EOFError, OSError) as e:
            raise ParseError(f"Invalid .tar.gz archive: {e}") from e

    def _extract_metadata(self, tar: tarfile.TarFile) -> dict[str, Any]:
        """Extract inputs, outputs, and README from tar archive members."""
        inputs: list[dict[str, Any]] = []
        outputs: list[dict[str, Any]] = []
        readme: str | None = None
        tf_files_found = False

        for member in tar.getmembers():
            if not member.isfile():
                continue

            # Security: skip absolute paths and path traversal
            if member.name.startswith("/") or ".." in member.name:
                continue

            # Skip oversized files
            if member.size > _MAX_FILE_SIZE:
                continue

            basename = member.name.rsplit("/", 1)[-1].lower()

            if basename.endswith(".tf"):
                tf_files_found = True
                content = self._read_member(tar, member)
                if content is None:
                    continue

                # Extract variables from any .tf file (not just variables.tf)
                if "variables" in basename or "variable" in basename:
                    inputs.extend(self._parse_variables(content))
                elif "outputs" in basename or "output" in basename:
                    outputs.extend(self._parse_outputs(content))
                else:
                    # Also check other .tf files for variable/output blocks
                    inputs.extend(self._parse_variables(content))
                    outputs.extend(self._parse_outputs(content))

            elif basename == "readme.md":
                content = self._read_member(tar, member)
                if content is not None:
                    readme = content

        if not tf_files_found:
            raise ParseError(
                "Module package must contain at least one .tf file. "
                "No Terraform configuration files found in the archive."
            )

        # Deduplicate by name
        inputs = self._deduplicate(inputs)
        outputs = self._deduplicate(outputs)

        logger.info(
            "module_parsed",
            inputs_count=len(inputs),
            outputs_count=len(outputs),
            has_readme=readme is not None,
        )

        return {
            "inputs": inputs,
            "outputs": outputs,
            "readme": readme,
        }

    def _read_member(self, tar: tarfile.TarFile, member: tarfile.TarInfo) -> str | None:
        """Safely read and decode a tar member."""
        try:
            f = tar.extractfile(member)
            if f is None:
                return None
            data = f.read(_MAX_FILE_SIZE)
            return data.decode("utf-8", errors="replace")
        except Exception:
            logger.warning("failed_to_read_member", member=member.name)
            return None

    def _parse_variables(self, content: str) -> list[dict[str, Any]]:
        """Parse variable blocks from HCL content."""
        variables = []
        for match in _VARIABLE_BLOCK_RE.finditer(content):
            name = match.group(1)
            body = match.group(2)

            var_type = "string"
            type_match = _TYPE_RE.search(body)
            if type_match:
                var_type = type_match.group(1).strip().strip('"')

            description = None
            desc_match = _DESC_RE.search(body)
            if desc_match:
                description = desc_match.group(1)

            default = None
            has_default = False
            default_match = _DEFAULT_RE.search(body)
            if default_match:
                has_default = True
                default = default_match.group(1).strip().strip('"')

            variables.append(
                {
                    "name": name,
                    "type": var_type,
                    "description": description,
                    "default": default,
                    "required": not has_default,
                }
            )

        return variables

    def _parse_outputs(self, content: str) -> list[dict[str, Any]]:
        """Parse output blocks from HCL content."""
        results = []
        for match in _OUTPUT_BLOCK_RE.finditer(content):
            name = match.group(1)
            body = match.group(2)

            description = None
            desc_match = _DESC_RE.search(body)
            if desc_match:
                description = desc_match.group(1)

            results.append(
                {
                    "name": name,
                    "description": description,
                }
            )

        return results

    def _deduplicate(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate entries by name, keeping the first occurrence."""
        seen: set[str] = set()
        result = []
        for item in items:
            if item["name"] not in seen:
                seen.add(item["name"])
                result.append(item)
        return result
