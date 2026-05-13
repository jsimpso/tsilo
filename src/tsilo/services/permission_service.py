"""Permission service - namespace access control based on user groups."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.middleware.auth import CurrentUser
from tsilo.models.namespace import Namespace
from tsilo.models.permission import NamespacePermission, PermissionLevel
from tsilo.services.cache import permission_cache


class PermissionService:
    """Checks read/write access based on user groups and namespace permissions."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def check_read_access(self, user: CurrentUser, namespace_name: str) -> bool:
        """Check if user has read access to a namespace.

        A user has read access if any of their groups has read or write
        permission on the namespace. Results are cached for 1 minute.
        """
        if not user.groups:
            return False

        cache_key = f"read:{namespace_name}:{','.join(sorted(user.groups))}"
        cached = permission_cache.get(cache_key)
        if cached is not None:
            return bool(cached)

        stmt = (
            select(NamespacePermission)
            .join(
                NamespacePermission.namespace,
            )
            .where(
                NamespacePermission.namespace.has(name=namespace_name),
                NamespacePermission.group_name.in_(user.groups),
                NamespacePermission.permission_level.in_(
                    [PermissionLevel.READ, PermissionLevel.WRITE]
                ),
            )
        )
        result = await self._db.execute(stmt)
        has_access = result.scalar_one_or_none() is not None
        permission_cache.set(cache_key, has_access)
        return has_access

    async def check_write_access(self, user: CurrentUser, namespace_name: str) -> bool:
        """Check if user has write access to a namespace.

        A user has write access if any of their groups has write permission
        on the namespace. Results are cached for 1 minute.
        """
        if not user.groups:
            return False

        cache_key = f"write:{namespace_name}:{','.join(sorted(user.groups))}"
        cached = permission_cache.get(cache_key)
        if cached is not None:
            return bool(cached)

        stmt = (
            select(NamespacePermission)
            .join(
                NamespacePermission.namespace,
            )
            .where(
                NamespacePermission.namespace.has(name=namespace_name),
                NamespacePermission.group_name.in_(user.groups),
                NamespacePermission.permission_level == PermissionLevel.WRITE,
            )
        )
        result = await self._db.execute(stmt)
        has_access = result.scalar_one_or_none() is not None
        permission_cache.set(cache_key, has_access)
        return has_access

    async def get_user_readable_namespaces(self, user: CurrentUser) -> list[str]:
        """Get list of namespace names the user can read."""
        if not user.groups:
            return []

        from tsilo.models.namespace import Namespace

        stmt = (
            select(Namespace.name)
            .join(NamespacePermission, NamespacePermission.namespace_id == Namespace.id)
            .where(
                NamespacePermission.group_name.in_(user.groups),
                NamespacePermission.permission_level.in_(
                    [PermissionLevel.READ, PermissionLevel.WRITE]
                ),
            )
            .distinct()
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_namespace_permissions(self, namespace_name: str) -> list[dict[str, Any]]:
        """List all permissions for a namespace."""
        stmt = (
            select(NamespacePermission)
            .join(Namespace, NamespacePermission.namespace_id == Namespace.id)
            .where(Namespace.name == namespace_name)
            .order_by(NamespacePermission.group_name)
        )
        result = await self._db.execute(stmt)
        permissions = result.scalars().all()

        return [
            {
                "id": p.id,
                "group_name": p.group_name,
                "permission_level": p.permission_level.value,
                "created_at": p.created_at,
            }
            for p in permissions
        ]

    async def create_permission(
        self,
        namespace_name: str,
        group_name: str,
        permission_level: str,
    ) -> dict[str, Any]:
        """Create a new permission for a namespace.

        Raises ValueError if the permission already exists.
        """
        # Look up namespace
        ns_stmt = select(Namespace).where(Namespace.name == namespace_name)
        ns_result = await self._db.execute(ns_stmt)
        ns = ns_result.scalar_one_or_none()
        if ns is None:
            raise ValueError(f"Namespace '{namespace_name}' not found")

        level = PermissionLevel(permission_level)

        # Check for duplicate
        dup_stmt = select(NamespacePermission).where(
            NamespacePermission.namespace_id == ns.id,
            NamespacePermission.group_name == group_name,
            NamespacePermission.permission_level == level,
        )
        dup_result = await self._db.execute(dup_stmt)
        if dup_result.scalar_one_or_none() is not None:
            raise ValueError(
                f"Permission already exists: group '{group_name}' "
                f"with level '{permission_level}' on namespace '{namespace_name}'"
            )

        perm = NamespacePermission(
            namespace_id=ns.id,
            group_name=group_name,
            permission_level=level,
        )
        self._db.add(perm)
        await self._db.flush()

        # Invalidate permission cache for this namespace
        permission_cache.clear()

        return {
            "id": perm.id,
            "group_name": perm.group_name,
            "permission_level": perm.permission_level.value,
            "created_at": perm.created_at,
        }

    async def delete_permission(
        self,
        permission_id: uuid.UUID,
        namespace_name: str,
    ) -> bool:
        """Delete a permission by ID within a namespace.

        Returns True if deleted, False if not found.
        """
        stmt = (
            select(NamespacePermission)
            .join(Namespace, NamespacePermission.namespace_id == Namespace.id)
            .where(
                NamespacePermission.id == permission_id,
                Namespace.name == namespace_name,
            )
        )
        result = await self._db.execute(stmt)
        perm = result.scalar_one_or_none()

        if perm is None:
            return False

        await self._db.delete(perm)
        await self._db.flush()

        # Invalidate permission cache for this namespace
        permission_cache.clear()

        return True
