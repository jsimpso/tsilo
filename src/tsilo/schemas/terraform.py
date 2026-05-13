"""Pydantic schemas for Terraform Module Registry Protocol responses."""

from pydantic import BaseModel, Field


class LoginV1Config(BaseModel):
    """OAuth login configuration for Terraform CLI."""

    client: str = "terraform-cli"
    grant_types: list[str] = Field(default_factory=lambda: ["authz_code"])
    authz: str = "/oauth/authorization"
    token: str = "/oauth/token"  # noqa: S105
    ports: list[int] = Field(default_factory=lambda: [10000, 10010])


class ServiceDiscoveryResponse(BaseModel):
    """Response for /.well-known/terraform.json service discovery."""

    modules_v1: str = Field(alias="modules.v1", default="/v1/modules/")
    login_v1: LoginV1Config = Field(alias="login.v1", default_factory=LoginV1Config)

    model_config = {"populate_by_name": True}


class VersionEntry(BaseModel):
    """A single version in the versions list."""

    version: str


class ModuleVersionsEntry(BaseModel):
    """Module entry containing list of versions."""

    versions: list[VersionEntry]


class VersionsResponse(BaseModel):
    """Response for GET /v1/modules/:namespace/:name/:provider/versions."""

    modules: list[ModuleVersionsEntry]


class RegistryError(BaseModel):
    """Single error entry in Terraform-compatible error response."""

    status: str
    title: str
    detail: str


class ErrorResponse(BaseModel):
    """Terraform-compatible error response format."""

    errors: list[RegistryError]
