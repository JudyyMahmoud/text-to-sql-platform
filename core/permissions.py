"""
Resolves exactly which tables/columns a given user is allowed to see and
use, for a given connection. This is the single source of truth that both
the SQL-generation prompt AND the SQL validator/executor rely on — the LLM
never gets to decide what it can access, this module decides for it.
"""
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.tenant_context import TenantContext
from models.database_schema import DatabaseTable, DatabaseColumn
from models.table_permission import TablePermission, ColumnPermission


async def get_allowed_schema(
    db: AsyncSession, ctx: TenantContext, connection_id: UUID
) -> dict:
    """
    Returns a dict shaped like:
    {
        "customers": {
            "table_id": "...",
            "access": "read" | "read_write",
            "columns": ["id", "name", "country"],
            "row_filter": {...}
        },
        ...
    }
    Only tables/columns with an explicit, active permission grant for this
    user (directly, or via one of their roles) are included. Tenant admins
    still only see tables belonging to their own tenant, but they implicitly
    get read access to every enabled table on that connection so they can
    manage permissions.
    """
    # Load every enabled table for this connection & tenant.
    tables_result = await db.execute(
        select(DatabaseTable).where(
            DatabaseTable.tenant_id == ctx.tenant_id,
            DatabaseTable.connection_id == connection_id,
            DatabaseTable.is_enabled.is_(True),
        )
    )
    tables = {t.id: t for t in tables_result.scalars().all()}
    if not tables:
        return {}

    # Load permission grants that apply to this user: either directly
    # user-scoped, or granted through one of the user's roles.
    subject_filter = [TablePermission.user_id == ctx.user_id]
    if ctx.role_ids:
        subject_filter.append(TablePermission.role_id.in_(ctx.role_ids))

    perms_result = await db.execute(
        select(TablePermission).where(
            TablePermission.tenant_id == ctx.tenant_id,
            TablePermission.connection_id == connection_id,
            TablePermission.can_read.is_(True),
            or_(*subject_filter),
        )
    )
    permissions = perms_result.scalars().all()

    # Tenant admins with zero explicit grants still get full read access to
    # enabled tables on their own tenant's connection (they own the data).
    if not permissions and ctx.is_tenant_admin:
        allowed_schema: dict = {}
        for table in tables.values():
            columns_result = await db.execute(
                select(DatabaseColumn).where(DatabaseColumn.table_id == table.id)
            )
            columns = columns_result.scalars().all()
            allowed_schema[table.table_name] = {
                "table_id": str(table.id),
                "access": "read_write",
                "columns": [c.column_name for c in columns if not c.is_sensitive],
                "row_filter": {},
            }
        return allowed_schema

    # Otherwise, build the schema strictly from explicit grants.
    allowed_schema: dict = {}
    for perm in permissions:
        table = tables.get(perm.table_id)
        if table is None:
            continue  # table disabled or not part of this connection

        access = "read_write" if (perm.can_insert or perm.can_update or perm.can_delete) else "read"

        col_perms_result = await db.execute(
            select(ColumnPermission).where(
                ColumnPermission.table_permission_id == perm.id,
                ColumnPermission.can_read.is_(True),
            )
        )
        col_perms = col_perms_result.scalars().all()

        if col_perms:
            column_ids = [cp.column_id for cp in col_perms]
            cols_result = await db.execute(
                select(DatabaseColumn).where(DatabaseColumn.id.in_(column_ids))
            )
            column_names = [c.column_name for c in cols_result.scalars().all()]
        else:
            # No column-level restriction defined -> allow all non-sensitive columns.
            cols_result = await db.execute(
                select(DatabaseColumn).where(
                    DatabaseColumn.table_id == table.id, DatabaseColumn.is_sensitive.is_(False)
                )
            )
            column_names = [c.column_name for c in cols_result.scalars().all()]

        allowed_schema[table.table_name] = {
            "table_id": str(table.id),
            "access": access,
            "columns": column_names,
            "row_filter": perm.row_filter or {},
        }

    return allowed_schema
