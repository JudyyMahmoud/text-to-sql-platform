from urllib.parse import quote_plus

from services.database.adapters.base import BaseAdapter


class SQLServerAdapter(BaseAdapter):
    """
    NOTE: to actually connect, install `pyodbc` plus the "ODBC Driver 18
    for SQL Server" system package and add it to requirements.txt /
    Dockerfile. The adapter interface is ready; only the driver install
    is left, by design, so the platform stays lightweight by default.
    """

    dialect_name = "sqlserver"

    def build_sqlalchemy_url(
        self, host: str, port: int, database: str, username: str, password: str, ssl_enabled: bool
    ) -> str:
        pwd = quote_plus(password)
        user = quote_plus(username)
        driver = quote_plus("ODBC Driver 18 for SQL Server")
        encrypt = "yes" if ssl_enabled else "no"
        return (
            f"mssql+pyodbc://{user}:{pwd}@{host}:{port}/{database}"
            f"?driver={driver}&Encrypt={encrypt}&TrustServerCertificate=yes"
        )

    def default_port(self) -> int:
        return 1433
