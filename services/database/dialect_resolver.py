from app.exceptions import AppError
from core.constants import SUPPORTED_DB_TYPES
from services.database.adapters.base import BaseAdapter
from services.database.adapters.mysql import MySQLAdapter
from services.database.adapters.oracle import OracleAdapter
from services.database.adapters.postgresql import PostgreSQLAdapter
from services.database.adapters.sqlserver import SQLServerAdapter

_ADAPTERS: dict[str, BaseAdapter] = {
    "postgresql": PostgreSQLAdapter(),
    "mysql": MySQLAdapter(),
    "sqlserver": SQLServerAdapter(),
    "oracle": OracleAdapter(),
}


def get_adapter(database_type: str) -> BaseAdapter:
    if database_type not in SUPPORTED_DB_TYPES:
        raise AppError(
            f"Unsupported database_type '{database_type}'. Supported: {SUPPORTED_DB_TYPES}"
        )
    return _ADAPTERS[database_type]
