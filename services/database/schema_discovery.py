from uuid import UUID

from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.encryption import decrypt_value
from models.database_connection import DatabaseConnection
from models.database_schema import DatabaseSchema, DatabaseTable, DatabaseColumn
from services.database.dialect_resolver import get_adapter


def _build_url(conn: DatabaseConnection) -> str:
    adapter = get_adapter(conn.database_type)
    password = decrypt_value(conn.encrypted_password) or ""
    return adapter.build_sqlalchemy_url(
        conn.host, conn.port, conn.database_name, conn.username, password, conn.ssl_enabled
    )


async def discover_and_cache_schema(db: AsyncSession, tenant_id: UUID, conn: DatabaseConnection) -> dict:
    """
    Connects to the live customer database, reflects its schemas / tables /
    columns via SQLAlchemy's Inspector, and upserts that metadata into the
    platform's own application database. No customer row data is copied —
    only structural metadata.
    """
    url = _build_url(conn)
    engine = create_engine(url, connect_args={"connect_timeout": 10} if conn.database_type != "sqlserver" else {})
    try:
        inspector = inspect(engine)
        schema_names = inspector.get_schema_names()
        # Skip noisy system schemas so the cache stays relevant.
        ignore = {"information_schema", "pg_catalog", "pg_toast", "sys", "mysql", "performance_schema"}
        schema_names = [s for s in schema_names if s.lower() not in ignore] or [None]

        tables_discovered = 0
        columns_discovered = 0

        for schema_name in schema_names:
            db_schema = None
            if schema_name:
                result = await db.execute(
                    select(DatabaseSchema).where(
                        DatabaseSchema.connection_id == conn.id, DatabaseSchema.schema_name == schema_name
                    )
                )
                db_schema = result.scalar_one_or_none()
                if db_schema is None:
                    db_schema = DatabaseSchema(tenant_id=tenant_id, connection_id=conn.id, schema_name=schema_name)
                    db.add(db_schema)
                    await db.flush()

            table_names = inspector.get_table_names(schema=schema_name)
            for table_name in table_names:
                result = await db.execute(
                    select(DatabaseTable).where(
                        DatabaseTable.connection_id == conn.id,
                        DatabaseTable.table_name == table_name,
                        DatabaseTable.schema_id == (db_schema.id if db_schema else None),
                    )
                )
                db_table = result.scalar_one_or_none()
                pk_constraint = inspector.get_pk_constraint(table_name, schema=schema_name)
                pk_columns = pk_constraint.get("constrained_columns", []) if pk_constraint else []

                if db_table is None:
                    db_table = DatabaseTable(
                        tenant_id=tenant_id,
                        connection_id=conn.id,
                        schema_id=db_schema.id if db_schema else None,
                        table_name=table_name,
                        table_type="table",
                        primary_key_columns=pk_columns,
                    )
                    db.add(db_table)
                else:
                    db_table.primary_key_columns = pk_columns
                await db.flush()
                tables_discovered += 1

                fks = inspector.get_foreign_keys(table_name, schema=schema_name)
                fk_map = {}
                for fk in fks:
                    for local_col, remote_col in zip(fk.get("constrained_columns", []), fk.get("referred_columns", [])):
                        fk_map[local_col] = {
                            "referenced_schema": fk.get("referred_schema"),
                            "referenced_table": fk.get("referred_table"),
                            "referenced_column": remote_col,
                        }

                columns = inspector.get_columns(table_name, schema=schema_name)
                for position, col in enumerate(columns, start=1):
                    col_name = col["name"]
                    result = await db.execute(
                        select(DatabaseColumn).where(
                            DatabaseColumn.table_id == db_table.id, DatabaseColumn.column_name == col_name
                        )
                    )
                    db_col = result.scalar_one_or_none()
                    is_fk = col_name in fk_map

                    if db_col is None:
                        db_col = DatabaseColumn(
                            tenant_id=tenant_id,
                            table_id=db_table.id,
                            column_name=col_name,
                            data_type=str(col["type"]),
                            ordinal_position=position,
                            is_nullable=col.get("nullable", True),
                            is_primary_key=col_name in pk_columns,
                            is_foreign_key=is_fk,
                            referenced_schema=fk_map.get(col_name, {}).get("referenced_schema"),
                            referenced_table=fk_map.get(col_name, {}).get("referenced_table"),
                            referenced_column=fk_map.get(col_name, {}).get("referenced_column"),
                        )
                        db.add(db_col)
                    else:
                        db_col.data_type = str(col["type"])
                        db_col.ordinal_position = position
                        db_col.is_nullable = col.get("nullable", True)
                        db_col.is_primary_key = col_name in pk_columns
                        db_col.is_foreign_key = is_fk
                    columns_discovered += 1

        await db.flush()
        return {"tables_discovered": tables_discovered, "columns_discovered": columns_discovered}
    finally:
        engine.dispose()
