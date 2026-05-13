"""Pydantic schemas for metrics API - overview, module metrics, download trends."""

from datetime import datetime

from pydantic import BaseModel


class TopModule(BaseModel):
    """Top module entry in metrics overview."""

    namespace: str
    name: str
    system: str
    downloads: int


class NamespaceUsage(BaseModel):
    """Namespace usage statistics."""

    namespace: str
    module_count: int
    version_count: int
    total_downloads: int


class MetricsOverviewData(BaseModel):
    """System-wide metrics data."""

    total_modules: int
    total_versions: int
    total_namespaces: int
    total_downloads: int
    downloads_last_30_days: int
    active_users_last_30_days: int
    top_modules: list[TopModule]
    namespace_usage: list[NamespaceUsage]


class MetricsOverviewResponse(BaseModel):
    """Response for GET /api/metrics/overview."""

    metrics: MetricsOverviewData


class VersionDownloadInfo(BaseModel):
    """Per-version download statistics."""

    version: str
    download_count: int
    last_download_at: datetime | None = None
    deprecated: bool = False


class DailyDownload(BaseModel):
    """Daily download count."""

    date: str
    count: int


class ModuleMetricsData(BaseModel):
    """Detailed metrics for a specific module."""

    total_downloads: int
    downloads_by_version: list[VersionDownloadInfo]
    downloads_over_time: list[DailyDownload]


class ModuleIdentifier(BaseModel):
    """Module identifier in metrics response."""

    namespace: str
    name: str
    system: str


class ModuleMetricsResponse(BaseModel):
    """Response for GET /api/metrics/modules/:namespace/:name/:system."""

    module: ModuleIdentifier
    metrics: ModuleMetricsData
