from sqlalchemy import create_engine, text

from services.database.dialect_resolver import get_adapter


def test_connection(
    database_type: str, host: str, port: int, database_name: str, username: str, password: str, ssl_enabled: bool
) -> tuple[bool, str]:
    """
    Tries to open a short-lived connection and run `SELECT 1`.
    Returns (success, message). Never raises — callers get a clean result.
    """
    adapter = get_adapter(database_type)
    url = adapter.build_sqlalchemy_url(host, port, database_name, username, password, ssl_enabled)
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 5} if database_type != "sqlserver" else {})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True, "Connection successful."
    except Exception as exc:
        # Trim overly verbose driver errors but keep them informative.
        return False, f"Connection failed: {str(exc)[:300]}"
