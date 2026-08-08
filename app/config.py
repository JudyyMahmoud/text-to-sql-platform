"""
Central configuration for the whole application.
Everything is loaded from environment variables (see .env.example).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application database (platform DB)
    APP_DB_HOST: str = "localhost"
    APP_DB_PORT: int = 5432
    APP_DB_NAME: str = "platform_db"
    APP_DB_USER: str = "platform_user"
    APP_DB_PASSWORD: str = "platform_password"
    APP_DATABASE_URL: str | None = None

    # Security
    JWT_SECRET_KEY: str = "insecure-dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    ENCRYPTION_KEY: str = ""

    # LLM (chat / SQL generation / answers) — any OpenAI-compatible provider works,
    # including Groq. Set OPENAI_BASE_URL and LLM_MODEL accordingly.
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"

    # Embeddings — run locally via fastembed (free, no API key, no external
    # provider needed) since not every LLM provider (e.g. Groq) offers embeddings.
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSIONS: int = 384

    # File storage
    FILE_STORAGE_PATH: str = "./storage/files"

    # SQL safety
    SQL_MAX_ROWS: int = 1000
    SQL_TIMEOUT_SECONDS: int = 15

    # General
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Seeded on first boot so you have something to log in with immediately.
    DEFAULT_TENANT_NAME: str = "Demo Company"
    DEFAULT_TENANT_CODE: str = "demo"
    DEFAULT_ADMIN_EMAIL: str = "admin@demo.com"
    DEFAULT_ADMIN_PASSWORD: str = "ChangeMe123!"

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.APP_DATABASE_URL:
            return self.APP_DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.APP_DB_USER}:{self.APP_DB_PASSWORD}"
            f"@{self.APP_DB_HOST}:{self.APP_DB_PORT}/{self.APP_DB_NAME}"
        )

    @property
    def sqlalchemy_sync_database_url(self) -> str:
        """Used by Alembic, which works synchronously."""
        if self.APP_DATABASE_URL:
            return self.APP_DATABASE_URL.replace("+asyncpg", "")
        return (
            f"postgresql+psycopg2://{self.APP_DB_USER}:{self.APP_DB_PASSWORD}"
            f"@{self.APP_DB_HOST}:{self.APP_DB_PORT}/{self.APP_DB_NAME}"
        )


settings = Settings()
