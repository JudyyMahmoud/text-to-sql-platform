from abc import ABC, abstractmethod


class BaseAdapter(ABC):
    """
    Common interface every customer-database adapter must implement.
    Adapters are intentionally thin: they only know how to build a
    connection URL and which SQLAlchemy driver to use. All actual
    querying/reflection logic is shared and lives in schema_discovery.py
    and query_executor.py, keeping the platform "generic" rather than
    having one code path per customer/table.
    """

    dialect_name: str

    @abstractmethod
    def build_sqlalchemy_url(
        self, host: str, port: int, database: str, username: str, password: str, ssl_enabled: bool
    ) -> str:
        ...

    @abstractmethod
    def default_port(self) -> int:
        ...
