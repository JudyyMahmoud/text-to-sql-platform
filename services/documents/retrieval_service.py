from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.tenant_context import TenantContext
from models.document_chunk import DocumentChunk
from models.file import File
from services.documents.embedding_service import embed_query


async def retrieve_relevant_chunks(
    db: AsyncSession,
    ctx: TenantContext,
    query_text: str,
    knowledge_base_ids: list[UUID],
    top_k: int = 6,
) -> list[dict]:
    """
    Embeds the query and finds the closest document chunks (cosine distance
    via pgvector's `<=>` operator) restricted to the current tenant and the
    knowledge bases selected for this conversation.
    """
    if not knowledge_base_ids:
        return []

    query_embedding = await embed_query(query_text)
    if not query_embedding:
        return []

    result = await db.execute(
        select(DocumentChunk, File.original_name)
        .join(File, File.id == DocumentChunk.file_id)
        .where(
            DocumentChunk.tenant_id == ctx.tenant_id,
            DocumentChunk.knowledge_base_id.in_(knowledge_base_ids),
        )
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    rows = result.all()

    evidence = []
    for chunk, file_name in rows:
        evidence.append(
            {
                "chunk_id": chunk.id,
                "file_id": chunk.file_id,
                "file_name": file_name,
                "content": chunk.content,
                "page_number": chunk.page_number,
            }
        )
    return evidence
