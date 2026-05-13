"""Namespace service - listing, creating, and managing namespaces with permissions."""

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from tsilo.middleware.auth import CurrentUser
from tsilo.models.module import Module
from tsilo.models.namespace import Namespace
from tsilo.models.permission import NamespacePermission, PermissionLevel

logger = structlog.get_logger(__name__)


class NamespaceService:
    """Service for namespace CRUD and permission-aware listing."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_user_namespaces(self, user: CurrentUser) -> list[dict]:
        """List namespaces the user has access to, with module counts and permissions."""
        if not user.groups:
            return []

        # Get namespaces where user has any permission
        stmt = (
            select(Namespace)
            .join(NamespacePermission, NamespacePermission.namespace_id == Namespace.id)
            .where(
                NamespacePermission.group_name.in_(user.groups),
                NamespacePermission.permission_level.in_(
                    [PermissionLevel.READ, PermissionLevel.WRITE]
                ),
            )
            .distinct()
            .options(joinedload(Namespace.permissions))
        )
        result = await self._db.execute(stmt)
        namespaces = result.unique().scalars().all()

        items = []
        for ns in namespaces:
            # Count modules in this namespace
            count_stmt = select(func.count()).select_from(Module).where(
                Module.namespace_id == ns.id
            )
            count_result = await self._db.execute(count_stmt)
            module_count = count_result.scalar() or 0

            # Determine user's permission levels for this namespace
            user_perms = set()
            for perm in ns.permissions:
                if perm.group_name in user.groups:
                    user_perms.add(perm.permission_level.value)
                    if perm.permission_level == PermissionLevel.WRITE:
                        user_perms.add("read")  # write implies read

            items.append(
                {
                    "id": ns.id,
                    "name": ns.name,
                    "display_name": ns.display_name,
                    "description": ns.description,
                    "module_count": module_count,
                    "permissions": sorted(user_perms),
                    "created_at": ns.created_at,
                }
            )

        return items

    async def create_namespace(
        self,
        name: str,
        display_name: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Create a new namespace.

        Raises ValueError if namespace name already exists.
        """
        # Check for duplicate name
        existing = await self._db.execute(
            select(Namespace).where(Namespace.name == name)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError(f"Namespace '{name}' already exists")

        ns = Namespace(
            name=name,
            display_name=display_name,
            description=description,
        )
        self._db.add(ns)
        await self._db.flush()

        logger.info("namespace_created", namespace=name)

        return {
            "id": ns.id,
            "name": ns.name,
            "display_name": ns.display_name,
            "description": ns.description,
            "module_count": 0,
            "created_at": ns.created_at,
        }

    async def get_namespace_by_name(self, name: str) -> Namespace | None:
        """Get a namespace by its name."""
        result = await self._db.execute(
            select(Namespace).where(Namespace.name == name)
        )
        return result.scalar_one_or_none()
