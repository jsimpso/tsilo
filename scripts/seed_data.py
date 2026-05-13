"""Development data seeding script.

Creates sample namespaces, users, permissions, modules, and versions
for local development and testing.

Usage:
    python -m scripts.seed_data
"""

import asyncio
import hashlib
import io
import tarfile
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from tsilo.config import get_settings
from tsilo.models import Base, get_engine, get_session_factory
from tsilo.models.metric import DownloadMetric
from tsilo.models.module import Module
from tsilo.models.namespace import Namespace
from tsilo.models.permission import NamespacePermission, PermissionLevel
from tsilo.models.user import User
from tsilo.models.version import ModuleVersion

NOW = datetime.now(tz=timezone.utc)


def _make_tar_gz(files: dict[str, str]) -> bytes:
    """Create an in-memory .tar.gz from a dict of {path: content}."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return buf.read()


# ── Sample Data ──────────────────────────────────────────────────────────────

NAMESPACES = [
    {"name": "platform-team", "display_name": "Platform Team", "description": "Core infrastructure modules"},
    {"name": "networking", "display_name": "Networking", "description": "Network and connectivity modules"},
    {"name": "security", "display_name": "Security", "description": "Security and compliance modules"},
]

USERS = [
    {
        "oidc_sub": "dev|admin-001",
        "email": "admin@example.com",
        "name": "Admin User",
        "groups": ["platform-team-admins", "tsilo-admins"],
    },
    {
        "oidc_sub": "dev|dev-001",
        "email": "developer@example.com",
        "name": "Dev User",
        "groups": ["platform-team-developers", "networking-developers"],
    },
    {
        "oidc_sub": "dev|viewer-001",
        "email": "viewer@example.com",
        "name": "Viewer User",
        "groups": ["platform-team-viewers"],
    },
]

PERMISSIONS = [
    ("platform-team", "platform-team-admins", PermissionLevel.WRITE),
    ("platform-team", "platform-team-developers", PermissionLevel.WRITE),
    ("platform-team", "platform-team-viewers", PermissionLevel.READ),
    ("networking", "networking-developers", PermissionLevel.WRITE),
    ("networking", "platform-team-admins", PermissionLevel.READ),
    ("security", "platform-team-admins", PermissionLevel.WRITE),
    ("security", "tsilo-admins", PermissionLevel.WRITE),
]

MODULES = [
    {
        "namespace": "platform-team",
        "name": "vpc",
        "system": "aws",
        "description": "Creates a VPC with public and private subnets",
        "versions": [
            {
                "version": "1.0.0",
                "inputs": [
                    {
                        "name": "vpc_cidr",
                        "type": "string",
                        "description": "CIDR block for the VPC",
                        "default": "10.0.0.0/16",
                        "required": False,
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "description": "Name tag for the VPC",
                        "default": None,
                        "required": True,
                    },
                ],
                "outputs": [
                    {"name": "vpc_id", "description": "The ID of the VPC"},
                    {"name": "public_subnet_ids", "description": "List of public subnet IDs"},
                ],
                "readme": '# VPC Module\n\nCreates an AWS VPC with public and private subnets.\n\n## Usage\n\n```hcl\nmodule "vpc" {\n  source  = "tsilo.example.com/platform-team/vpc/aws"\n  version = "~> 1.0"\n  name    = "production"\n}\n```',
                "downloads": 150,
            },
            {
                "version": "2.0.0",
                "inputs": [
                    {
                        "name": "vpc_cidr",
                        "type": "string",
                        "description": "CIDR block for the VPC",
                        "default": "10.0.0.0/16",
                        "required": False,
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "description": "Name tag for the VPC",
                        "default": None,
                        "required": True,
                    },
                    {
                        "name": "enable_nat",
                        "type": "bool",
                        "description": "Enable NAT gateway",
                        "default": "true",
                        "required": False,
                    },
                ],
                "outputs": [
                    {"name": "vpc_id", "description": "The ID of the VPC"},
                    {"name": "public_subnet_ids", "description": "List of public subnet IDs"},
                    {"name": "nat_gateway_id", "description": "NAT gateway ID"},
                ],
                "readme": "# VPC Module v2\n\nCreates an AWS VPC with NAT gateway support.\n\n## Upgrade from v1\n\nAdd `enable_nat = true` to your configuration.",
                "downloads": 42,
            },
        ],
    },
    {
        "namespace": "platform-team",
        "name": "eks-cluster",
        "system": "aws",
        "description": "Managed Kubernetes cluster on AWS EKS",
        "versions": [
            {
                "version": "1.0.0",
                "inputs": [
                    {
                        "name": "cluster_name",
                        "type": "string",
                        "description": "Name of the EKS cluster",
                        "default": None,
                        "required": True,
                    },
                    {
                        "name": "kubernetes_version",
                        "type": "string",
                        "description": "Kubernetes version",
                        "default": "1.28",
                        "required": False,
                    },
                ],
                "outputs": [
                    {"name": "cluster_endpoint", "description": "EKS cluster API endpoint"},
                    {"name": "cluster_arn", "description": "EKS cluster ARN"},
                ],
                "readme": "# EKS Cluster Module\n\nDeploys a managed Kubernetes cluster.",
                "downloads": 88,
            },
        ],
    },
    {
        "namespace": "networking",
        "name": "cloudfront-cdn",
        "system": "aws",
        "description": "CloudFront CDN distribution with S3 origin",
        "versions": [
            {
                "version": "1.0.0",
                "inputs": [
                    {
                        "name": "domain_name",
                        "type": "string",
                        "description": "Domain for the CDN",
                        "default": None,
                        "required": True,
                    },
                    {
                        "name": "origin_bucket",
                        "type": "string",
                        "description": "S3 bucket name for origin",
                        "default": None,
                        "required": True,
                    },
                ],
                "outputs": [
                    {"name": "distribution_id", "description": "CloudFront distribution ID"},
                    {"name": "domain_name", "description": "CloudFront domain name"},
                ],
                "readme": "# CloudFront CDN Module\n\nCreates a CloudFront distribution backed by S3.",
                "downloads": 25,
            },
        ],
    },
    {
        "namespace": "security",
        "name": "iam-role",
        "system": "aws",
        "description": "IAM role with configurable trust policy",
        "versions": [
            {
                "version": "1.0.0",
                "inputs": [
                    {
                        "name": "role_name",
                        "type": "string",
                        "description": "Name of the IAM role",
                        "default": None,
                        "required": True,
                    },
                    {
                        "name": "trusted_services",
                        "type": "list(string)",
                        "description": "AWS services allowed to assume the role",
                        "default": None,
                        "required": True,
                    },
                ],
                "outputs": [
                    {"name": "role_arn", "description": "ARN of the IAM role"},
                ],
                "readme": "# IAM Role Module\n\nCreates an IAM role with configurable trust relationships.",
                "downloads": 60,
            },
        ],
    },
]


async def seed():
    """Seed the database with sample data."""
    settings = get_settings()
    print(f"Seeding database: {settings.database_url}")

    factory = get_session_factory()
    async with factory() as session:
        # Check if data already exists
        existing = await session.execute(select(Namespace).limit(1))
        if existing.scalar_one_or_none() is not None:
            print("Database already has data. Skipping seed.")
            return

        # Create namespaces
        ns_map: dict[str, Namespace] = {}
        for ns_data in NAMESPACES:
            ns = Namespace(**ns_data)
            session.add(ns)
            ns_map[ns_data["name"]] = ns
        await session.flush()
        print(f"Created {len(NAMESPACES)} namespaces")

        # Create users
        user_map: dict[str, User] = {}
        for user_data in USERS:
            user = User(**user_data, last_login_at=NOW)
            session.add(user)
            user_map[user_data["email"]] = user
        await session.flush()
        print(f"Created {len(USERS)} users")

        # Create permissions
        for ns_name, group, level in PERMISSIONS:
            perm = NamespacePermission(
                namespace_id=ns_map[ns_name].id,
                group_name=group,
                permission_level=level,
            )
            session.add(perm)
        await session.flush()
        print(f"Created {len(PERMISSIONS)} permissions")

        # Create modules and versions
        publisher = user_map["admin@example.com"]
        version_count = 0
        for mod_data in MODULES:
            ns = ns_map[mod_data["namespace"]]
            module = Module(
                namespace_id=ns.id,
                name=mod_data["name"],
                system=mod_data["system"],
                description=mod_data["description"],
            )
            session.add(module)
            await session.flush()

            for ver_data in mod_data["versions"]:
                # Create a minimal tar.gz for the package_url
                fake_package = _make_tar_gz({"module/main.tf": 'resource "null_resource" "seed" {}'})
                checksum = hashlib.sha256(fake_package).hexdigest()

                mv = ModuleVersion(
                    module_id=module.id,
                    version=ver_data["version"],
                    inputs=ver_data["inputs"],
                    outputs=ver_data["outputs"],
                    readme=ver_data["readme"],
                    package_url=f"s3://tsilo-modules/{mod_data['namespace']}/{mod_data['name']}/{mod_data['system']}/{ver_data['version']}/module.tar.gz",
                    package_size_bytes=len(fake_package),
                    checksum_sha256=checksum,
                    published_by=publisher.id,
                    published_at=NOW - timedelta(days=30),
                )
                session.add(mv)
                await session.flush()

                # Create download metric
                dl = DownloadMetric(
                    version_id=mv.id,
                    download_count=ver_data["downloads"],
                    last_download_at=NOW - timedelta(days=2) if ver_data["downloads"] > 0 else None,
                )
                session.add(dl)
                version_count += 1

        await session.commit()
        print(f"Created {len(MODULES)} modules with {version_count} versions")
        print("Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())
