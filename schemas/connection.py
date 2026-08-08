from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DatabaseConnectionCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    database_type: str = Field(..., description="postgresql | mysql | sqlserver | oracle")
    host: str
    port: int
    database_name: str
    username: str
    password: str
    ssl_enabled: bool = False
    connection_options: dict = Field(default_factory=dict)


class DatabaseConnectionUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    username: str | None = None
    password: str | None = None
    ssl_enabled: bool | None = None
    is_active: bool | None = None


class DatabaseConnectionResponse(BaseModel):
    id: UUID
    name: str
    database_type: str
    host: str | None
    port: int | None
    database_name: str | None
    username: str | None
    ssl_enabled: bool
    status: str
    last_tested_at: datetime | None
    last_test_message: str | None
    schema_sync_status: str | None
    last_schema_sync_at: datetime | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str


class TableResponse(BaseModel):
    id: UUID
    table_name: str
    table_type: str
    estimated_row_count: int | None
    is_enabled: bool
    is_sensitive: bool

    class Config:
        from_attributes = True


class ColumnResponse(BaseModel):
    id: UUID
    column_name: str
    data_type: str
    is_primary_key: bool
    is_foreign_key: bool
    is_sensitive: bool

    class Config:
        from_attributes = True


class SchemaSyncResponse(BaseModel):
    schema_sync_status: str
    tables_discovered: int
    columns_discovered: int
