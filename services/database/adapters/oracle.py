from urllib.parse import quote_plus

from services.database.adapters.base import BaseAdapter


class OracleAdapter(BaseAdapter):
    """
    NOTE: to actually connect, install `oracledb` and add it to
    requirements.txt. The adapter interface is ready; only the driver
    install is left, by design, so the platform stays lightweight by default.
    """

    dialect_name = "oracle"

    def build_sqlalchemy_url(
        self, host: str, port: int, database: str, username: str, password: str, ssl_enabled: bool
    ) -> str:
        pwd = quote_plus(password)
        user = quote_plus(username)
        return f"oracle+oracledb://{user}:{pwd}@{host}:{port}/?service_name={database}"

    def default_port(self) -> int:
        return 1521
