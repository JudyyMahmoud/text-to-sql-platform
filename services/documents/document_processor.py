import hashlib
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from core.constants import ProcessingStatus
from models.document_chunk import DocumentChunk
from models.file import File
from services.documents.chunking_service import chunk_pages
from services.documents.embedding_service import embed_chunks
from services.documents.parsers import parse_file


async def process_file(db: AsyncSession, file_record: File) -> None:
    """
    Runs the full ingestion pipeline for one uploaded file:
    parse -> chunk -> embed -> store in document_chunks.
    Updates file_record.processing_status along the way.
    """
    file_record.processing_status = ProcessingStatus.PROCESSING
    await db.commit()

    try:
        pages = parse_file(file_record.storage_path, file_record.extension)
        chunks = chunk_pages(pages)

        if not chunks:
            file_record.processing_status = ProcessingStatus.FAILED
            file_record.processing_error = "No extractable text was found in this file."
            await db.commit()
            return

        embeddings = await embed_chunks([c["content"] for c in chunks])

        total_text_length = 0
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            content = chunk["content"]
            total_text_length += len(content)
            db_chunk = DocumentChunk(
                tenant_id=file_record.tenant_id,
                knowledge_base_id=file_record.knowledge_base_id,
                file_id=file_record.id,
                chunk_index=idx,
                content=content,
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
                page_number=chunk["page_number"],
                token_count=max(1, len(content) // 4),
                embedding=embedding,
            )
            db.add(db_chunk)

        file_record.processing_status = ProcessingStatus.COMPLETED
        file_record.processing_error = None
        file_record.page_count = len({c["page_number"] for c in chunks if c["page_number"] is not None}) or None
        file_record.extracted_text_length = total_text_length
        file_record.processed_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        file_record.processing_status = ProcessingStatus.FAILED
        file_record.processing_error = str(exc)[:500]
        await db.commit()
