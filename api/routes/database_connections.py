from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_context, require_tenant_admin
from core.database import get_db
from core.tenant_context import TenantContext
from models.database_schema import DatabaseTable, DatabaseColumn
from schemas.connection import (
    ColumnResponse,
    ConnectionTestResponse,
    DatabaseConnectionCreate,
    DatabaseConnectionResponse,
    DatabaseConnectionUpdate,
    SchemaSyncResponse,
    TableResponse,
)
from services.database import connection_service

router = APIRouter(prefix="/api/database-connections", tags=["database-connections"])


@router.post("", response_model=DatabaseConnectionResponse, status_code=201)
async def create_connection(
    payload: DatabaseConnectionCreate,
    ctx: TenantContext = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_db),
):
    """Tenant admins add a live database connection at runtime — no source code changes needed."""
    conn = await connection_service.create_connection(db, ctx, payload)
    return DatabaseConnectionResponse.model_validate(conn)


@router.get("", response_model=list[DatabaseConnectionResponse])
async def list_connections(ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)):
    conns = await connection_service.list_connections(db, ctx)
    return [DatabaseConnectionResponse.model_validate(c) for c in conns]


@router.get("/{connection_id}", response_model=DatabaseConnectionResponse)
async def get_connection(
    connection_id: UUID, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)
):
    conn = await connection_service.get_connection(db, ctx, connection_id)
    return DatabaseConnectionResponse.model_validate(conn)


@router.put("/{connection_id}", response_model=DatabaseConnectionResponse)
async def update_connection(
    connection_id: UUID,
    payload: DatabaseConnectionUpdate,
    ctx: TenantContext = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.update_connection(db, ctx, connection_id, payload)
    return DatabaseConnectionResponse.model_validate(conn)


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: UUID, ctx: TenantContext = Depends(require_tenant_admin), db: AsyncSession = Depends(get_db)
):
    await connection_service.delete_connection(db, ctx, connection_id)


@router.post("/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_connection_endpoint(
    connection_id: UUID, ctx: TenantContext = Depends(require_tenant_admin), db: AsyncSession = Depends(get_db)
):
    success, message = await connection_service.test_and_update(db, ctx, connection_id)
    return ConnectionTestResponse(success=success, message=message)


@router.post("/{connection_id}/sync-schema", response_model=SchemaSyncResponse)
async def sync_schema_endpoint(
    connection_id: UUID, ctx: TenantContext = Depends(require_tenant_admin), db: AsyncSession = Depends(get_db)
):
    stats = await connection_service.sync_schema(db, ctx, connection_id)
    conn = await connection_service.get_connection(db, ctx, connection_id)
    return SchemaSyncResponse(
        schema_sync_status=conn.schema_sync_status,
        tables_discovered=stats["tables_discovered"],
        columns_discovered=stats["columns_discovered"],
    )


@router.get("/{connection_id}/schemas")
async def list_schemas(
    connection_id: UUID, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)
):
    from models.database_schema import DatabaseSchema

    await connection_service.get_connection(db, ctx, connection_id)  # ensures tenant ownership
    result = await db.execute(
        select(DatabaseSchema).where(
            DatabaseSchema.connection_id == connection_id, DatabaseSchema.tenant_id == ctx.tenant_id
        )
    )
    schemas = result.scalars().all()
    return [{"id": s.id, "schema_name": s.schema_name} for s in schemas]


@router.get("/{connection_id}/tables", response_model=list[TableResponse])
async def list_tables(
    connection_id: UUID, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)
):
    await connection_service.get_connection(db, ctx, connection_id)  # ensures tenant ownership
    result = await db.execute(
        select(DatabaseTable).where(
            DatabaseTable.connection_id == connection_id, DatabaseTable.tenant_id == ctx.tenant_id
        )
    )
    tables = result.scalars().all()
    return [TableResponse.model_validate(t) for t in tables]


@router.get("/{connection_id}/tables/{table_id}/columns", response_model=list[ColumnResponse])
async def list_columns(
    connection_id: UUID,
    table_id: UUID,
    ctx: TenantContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    await connection_service.get_connection(db, ctx, connection_id)
    result = await db.execute(
        select(DatabaseColumn).where(DatabaseColumn.table_id == table_id, DatabaseColumn.tenant_id == ctx.tenant_id)
    )
    columns = result.scalars().all()
    return [ColumnResponse.model_validate(c) for c in columns]
