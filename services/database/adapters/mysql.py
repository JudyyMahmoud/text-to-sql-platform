from urllib.parse import quote_plus

from services.database.adapters.base import BaseAdapter


class MySQLAdapter(BaseAdapter):
    dialect_name = "mysql"

    def build_sqlalchemy_url(
        self, host: str, port: int, database: str, username: str, password: str, ssl_enabled: bool
    ) -> str:
        pwd = quote_plus(password)
        user = quote_plus(username)
        url = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{database}"
        if ssl_enabled:
            url += "?ssl_verify_cert=true"
        return url

    def default_port(self) -> int:
        return 3306
