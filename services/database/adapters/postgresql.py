from urllib.parse import quote_plus

from services.database.adapters.base import BaseAdapter


class PostgreSQLAdapter(BaseAdapter):
    dialect_name = "postgresql"

    def build_sqlalchemy_url(
        self, host: str, port: int, database: str, username: str, password: str, ssl_enabled: bool
    ) -> str:
        pwd = quote_plus(password)
        user = quote_plus(username)
        url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{database}"
        if ssl_enabled:
            url += "?sslmode=require"
        return url

    def default_port(self) -> int:
        return 5432
