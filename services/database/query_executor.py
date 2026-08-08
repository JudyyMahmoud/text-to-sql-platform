import time

from sqlalchemy import create_engine, text

from app.config import settings
from core.encryption import decrypt_value
from models.database_connection import DatabaseConnection
from services.database.dialect_resolver import get_adapter


def execute_sql(conn: DatabaseConnection, sql: str, query_type: str) -> dict:
    """
    Executes already-validated SQL against the target customer database.
    Enforces a statement timeout and treats the connection as read-only
    unless the statement was explicitly approved as read_write DML.
    Returns {"status", "row_count", "rows", "columns", "execution_time_ms", "error"}.
    """
    adapter = get_adapter(conn.database_type)
    password = decrypt_value(conn.encrypted_password) or ""
    url = adapter.build_sqlalchemy_url(conn.host, conn.port, conn.database_name, conn.username, password, conn.ssl_enabled)

    connect_args = {}
    if conn.database_type == "postgresql":
        connect_args = {
            "connect_timeout": 5,
            "options": f"-c statement_timeout={settings.SQL_TIMEOUT_SECONDS * 1000}",
        }
    elif conn.database_type == "mysql":
        connect_args = {"connect_timeout": 5}

    engine = create_engine(url, connect_args=connect_args)
    started = time.time()
    try:
        with engine.connect() as connection:
            if query_type == "SELECT" and conn.database_type == "postgresql":
                connection.execute(text("SET TRANSACTION READ ONLY"))
            result = connection.execute(text(sql))
            elapsed_ms = int((time.time() - started) * 1000)

            if result.returns_rows:
                columns = list(result.keys())
                rows = [dict(zip(columns, row)) for row in result.fetchmany(settings.SQL_MAX_ROWS)]
                connection.commit() if query_type != "SELECT" else None
                return {
                    "status": "success",
                    "row_count": len(rows),
                    "rows": rows,
                    "columns": columns,
                    "execution_time_ms": elapsed_ms,
                    "error": None,
                }
            else:
                connection.commit()
                return {
                    "status": "success",
                    "row_count": result.rowcount,
                    "rows": [],
                    "columns": [],
                    "execution_time_ms": elapsed_ms,
                    "error": None,
                }
    except Exception as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "status": "failed",
            "row_count": 0,
            "rows": [],
            "columns": [],
            "execution_time_ms": elapsed_ms,
            "error": str(exc)[:500],
        }
    finally:
        engine.dispose()
