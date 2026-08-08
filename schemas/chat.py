from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = None
    database_connection_ids: list[UUID] = Field(default_factory=list)
    knowledge_base_ids: list[UUID] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    id: UUID
    title: str | None
    status: str
    active_connection_ids: list
    active_knowledge_base_ids: list
    created_at: datetime
    last_message_at: datetime | None

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    message: str = Field(..., min_length=1)
    database_connection_ids: list[UUID] = Field(default_factory=list)
    knowledge_base_ids: list[UUID] = Field(default_factory=list)
    stream: bool = False


class SQLInfo(BaseModel):
    query_execution_id: UUID | None = None
    query: str | None = None
    row_count: int | None = None


class CitationInfo(BaseModel):
    type: str
    file_name: str | None = None
    page: int | None = None
    table: str | None = None


class ChatResponse(BaseModel):
    message_id: UUID
    conversation_id: UUID
    answer: str
    intent: str
    sources_used: list[str]
    sql: SQLInfo | None = None
    citations: list[CitationInfo] = Field(default_factory=list)
