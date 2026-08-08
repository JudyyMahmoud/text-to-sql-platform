from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: str | None = None


class KnowledgeBaseResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    embedding_model: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class FileResponse(BaseModel):
    id: UUID
    knowledge_base_id: UUID | None
    original_name: str
    mime_type: str | None
    extension: str | None
    file_size_bytes: int | None
    processing_status: str
    processing_error: str | None
    page_count: int | None
    created_at: datetime

    class Config:
        from_attributes = True
