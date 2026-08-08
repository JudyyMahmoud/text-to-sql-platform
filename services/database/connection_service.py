from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError
from core.constants import ConnectionStatus, SchemaSyncStatus
from core.encryption import decrypt_value, encrypt_value
from core.tenant_context import TenantContext
from models.database_connection import DatabaseConnection
from schemas.connection import DatabaseConnectionCreate, DatabaseConnectionUpdate
from services.database.connection_tester import test_connection
from services.database.schema_discovery import discover_and_cache_schema


async def create_connection(
    db: AsyncSession, ctx: TenantContext, payload: DatabaseConnectionCreate
) -> DatabaseConnection:
    existing = await db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.tenant_id == ctx.tenant_id, DatabaseConnection.name == payload.name
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"A connection named '{payload.name}' already exists for this tenant.")

    conn = DatabaseConnection(
        tenant_id=ctx.tenant_id,
        created_by=ctx.user_id,
        name=payload.name,
        database_type=payload.database_type,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        encrypted_password=encrypt_value(payload.password),
        ssl_enabled=payload.ssl_enabled,
        connection_options=payload.connection_options,
        status=ConnectionStatus.PENDING,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


async def list_connections(db: AsyncSession, ctx: TenantContext) -> list[DatabaseConnection]:
    result = await db.execute(
        select(DatabaseConnection)
        .where(DatabaseConnection.tenant_id == ctx.tenant_id)
        .order_by(DatabaseConnection.created_at.desc())
    )
    return list(result.scalars().all())


async def get_connection(db: AsyncSession, ctx: TenantContext, connection_id: UUID) -> DatabaseConnection:
    result = await db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id, DatabaseConnection.tenant_id == ctx.tenant_id
        )
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise NotFoundError("Database connection not found.")
    return conn


async def update_connection(
    db: AsyncSession, ctx: TenantContext, connection_id: UUID, payload: DatabaseConnectionUpdate
) -> DatabaseConnection:
    conn = await get_connection(db, ctx, connection_id)
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        conn.encrypted_password = encrypt_value(data.pop("password"))
    for field, value in data.items():
        setattr(conn, field, value)
    await db.commit()
    await db.refresh(conn)
    return conn


async def delete_connection(db: AsyncSession, ctx: TenantContext, connection_id: UUID) -> None:
    conn = await get_connection(db, ctx, connection_id)
    await db.delete(conn)
    await db.commit()


async def test_and_update(db: AsyncSession, ctx: TenantContext, connection_id: UUID) -> tuple[bool, str]:
    conn = await get_connection(db, ctx, connection_id)
    password = decrypt_value(conn.encrypted_password) or ""
    success, message = test_connection(
        conn.database_type, conn.host, conn.port, conn.database_name, conn.username, password, conn.ssl_enabled
    )
    conn.status = ConnectionStatus.CONNECTED if success else ConnectionStatus.FAILED
    conn.last_tested_at = datetime.now(timezone.utc)
    conn.last_test_message = message
    await db.commit()
    return success, message


async def sync_schema(db: AsyncSession, ctx: TenantContext, connection_id: UUID) -> dict:
    conn = await get_connection(db, ctx, connection_id)
    conn.schema_sync_status = SchemaSyncStatus.SYNCING
    await db.commit()
    try:
        stats = await discover_and_cache_schema(db, ctx.tenant_id, conn)
        conn.schema_sync_status = SchemaSyncStatus.SYNCED
        conn.last_schema_sync_at = datetime.now(timezone.utc)
        await db.commit()
        return stats
    except Exception as exc:
        await db.rollback()
        conn.schema_sync_status = SchemaSyncStatus.FAILED
        await db.commit()
        raise exc
