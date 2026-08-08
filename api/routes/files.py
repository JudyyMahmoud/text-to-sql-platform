from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File as FastAPIFile, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_context
from app.exceptions import NotFoundError
from core.database import AsyncSessionLocal, get_db
from core.tenant_context import TenantContext
from models.file import File
from schemas.file import FileResponse
from services.documents.document_processor import process_file
from services.documents.upload_service import save_uploaded_file

router = APIRouter(prefix="/api/files", tags=["files"])


async def _process_file_in_background(file_id: UUID):
    """Runs in its own DB session since the request's session will already be closed."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(File).where(File.id == file_id))
        file_record = result.scalar_one_or_none()
        if file_record:
            await process_file(db, file_record)


@router.post("/upload", response_model=FileResponse, status_code=201)
async def upload_file(
    background_tasks: BackgroundTasks,
    knowledge_base_id: UUID,
    upload: UploadFile = FastAPIFile(...),
    ctx: TenantContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Uploads a file into a knowledge base. Parsing, chunking, and embedding
    happen asynchronously in the background so the upload responds instantly.
    """
    file_record = await save_uploaded_file(db, ctx, upload, knowledge_base_id)
    background_tasks.add_task(_process_file_in_background, file_record.id)
    return FileResponse.model_validate(file_record)


@router.get("", response_model=list[FileResponse])
async def list_files(ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(File).where(File.tenant_id == ctx.tenant_id))
    return [FileResponse.model_validate(f) for f in result.scalars().all()]


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(file_id: UUID, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(File).where(File.id == file_id, File.tenant_id == ctx.tenant_id))
    file_record = result.scalar_one_or_none()
    if file_record is None:
        raise NotFoundError("File not found.")
    return FileResponse.model_validate(file_record)


@router.delete("/{file_id}", status_code=204)
async def delete_file(file_id: UUID, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)):
    import os

    result = await db.execute(select(File).where(File.id == file_id, File.tenant_id == ctx.tenant_id))
    file_record = result.scalar_one_or_none()
    if file_record is None:
        raise NotFoundError("File not found.")
    if os.path.exists(file_record.storage_path):
        os.remove(file_record.storage_path)
    await db.delete(file_record)
    await db.commit()


@router.post("/{file_id}/reprocess", response_model=FileResponse)
async def reprocess_file(
    file_id: UUID,
    background_tasks: BackgroundTasks,
    ctx: TenantContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(File).where(File.id == file_id, File.tenant_id == ctx.tenant_id))
    file_record = result.scalar_one_or_none()
    if file_record is None:
        raise NotFoundError("File not found.")
    file_record.processing_status = "pending"
    await db.commit()
    background_tasks.add_task(_process_file_in_background, file_record.id)
    return FileResponse.model_validate(file_record)
