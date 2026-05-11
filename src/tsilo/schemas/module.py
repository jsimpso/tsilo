"""Pydantic schemas for web UI API - module list, detail, and version responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ModuleVersionSummary(BaseModel):
    """Version summary in module detail response."""

    version: str
    published_at: datetime
    download_count: int = 0
    last_download_at: datetime | None = None
    deprecated: bool = False
    deprecation_reason: str | None = None


class ModuleListItem(BaseModel):
    """Single module entry in the module list response."""

    id: uuid.UUID
    namespace: str
    name: str
    provider: str
    description: str | None = None
    latest_version: str | None = None
    version_count: int = 0
    total_downloads: int = 0
    last_updated: datetime | None = None


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    page: int
    per_page: int
    total_pages: int
    total_count: int


class ModuleListResponse(BaseModel):
    """Response for GET /api/modules."""

    modules: list[ModuleListItem]
    pagination: PaginationInfo


class ModuleDetailResponse(BaseModel):
    """Response for GET /api/modules/:namespace/:name/:provider."""

    module: "ModuleDetail"


class ModuleDetail(BaseModel):
    """Detailed module information with version list."""

    id: uuid.UUID
    namespace: str
    name: str
    provider: str
    description: str | None = None
    source_url: str | None = None
    created_at: datetime
    versions: list[ModuleVersionSummary]
    latest_version: str | None = None
    total_downloads: int = 0


class VersionInput(BaseModel):
    """Input variable from a Terraform module."""

    name: str
    type: str = "string"
    description: str | None = None
    default: str | None = None
    required: bool = True


class VersionOutput(BaseModel):
    """Output value from a Terraform module."""

    name: str
    description: str | None = None


class PublisherInfo(BaseModel):
    """Publisher details for a module version."""

    id: uuid.UUID
    name: str | None = None
    email: str


class VersionDetailResponse(BaseModel):
    """Response for GET /api/modules/:namespace/:name/:provider/:version."""

    version: "VersionDetail"


class VersionDetail(BaseModel):
    """Detailed version information with inputs, outputs, and README."""

    id: uuid.UUID
    module_id: uuid.UUID
    version: str
    inputs: list[VersionInput]
    outputs: list[VersionOutput]
    readme: str | None = None
    usage_example: str | None = None
    package_size_bytes: int
    checksum_sha256: str
    published_by: PublisherInfo | None = None
    published_at: datetime
    download_count: int = 0
    last_download_at: datetime | None = None
