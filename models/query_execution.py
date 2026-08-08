import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class QueryExecution(Base):
    __tablename__ = "query_executions"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False
    )
    generated_sql: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_sql: Mapped[str | None] = mapped_column(Text)
    query_type: Mapped[str | None] = mapped_column(String(30))
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False)
    validation_errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    applied_row_filters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    referenced_tables: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    referenced_columns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    execution_status: Mapped[str | None] = mapped_column(String(30))
    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    returned_row_count: Mapped[int | None] = mapped_column(Integer)
    result_preview: Mapped[dict | list | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
