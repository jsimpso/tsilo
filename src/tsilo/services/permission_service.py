"""Permission service - namespace access control based on user groups."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tsilo.middleware.auth import CurrentUser
from tsilo.models.permission import NamespacePermission, PermissionLevel


class PermissionService:
    """Checks read/write access based on user groups and namespace permissions."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def check_read_access(self, user: CurrentUser, namespace_name: str) -> bool:
        """Check if user has read access to a namespace.

        A user has read access if any of their groups has read or write
        permission on the namespace.
        """
        if not user.groups:
            return False

        stmt = (
            select(NamespacePermission)
            .join(
                NamespacePermission.namespace,
            )
            .where(
                NamespacePermission.namespace.has(name=namespace_name),
                NamespacePermission.group_name.in_(user.groups),
                NamespacePermission.permission_level.in_([PermissionLevel.READ, PermissionLevel.WRITE]),
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def check_write_access(self, user: CurrentUser, namespace_name: str) -> bool:
        """Check if user has write access to a namespace.

        A user has write access if any of their groups has write permission
        on the namespace.
        """
        if not user.groups:
            return False

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
        return result.scalar_one_or_none() is not None

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
                NamespacePermission.permission_level.in_([PermissionLevel.READ, PermissionLevel.WRITE]),
            )
            .distinct()
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
