import hashlib
import os
import uuid
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import AppError
from core.tenant_context import TenantContext
from models.file import File

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".xlsx", ".xls"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


async def save_uploaded_file(
    db: AsyncSession, ctx: TenantContext, upload: UploadFile, knowledge_base_id: uuid.UUID | None
) -> File:
    original_name = upload.filename or "unnamed"
    extension = os.path.splitext(original_name)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise AppError(
            f"Unsupported file type '{extension}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    tenant_dir = os.path.join(settings.FILE_STORAGE_PATH, str(ctx.tenant_id))
    os.makedirs(tenant_dir, exist_ok=True)

    stored_name = f"{uuid.uuid4()}{extension}"
    storage_path = os.path.join(tenant_dir, stored_name)

    hasher = hashlib.sha256()
    size_bytes = 0
    with open(storage_path, "wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size_bytes += len(chunk)
            if size_bytes > MAX_FILE_SIZE_BYTES:
                out.close()
                os.remove(storage_path)
                raise AppError("File exceeds the 50MB upload limit.")
            hasher.update(chunk)
            out.write(chunk)

    file_record = File(
        tenant_id=ctx.tenant_id,
        knowledge_base_id=knowledge_base_id,
        uploaded_by=ctx.user_id,
        original_name=original_name,
        stored_name=stored_name,
        storage_path=storage_path,
        mime_type=upload.content_type,
        extension=extension,
        file_size_bytes=size_bytes,
        checksum=hasher.hexdigest(),
        processing_status="pending",
    )
    db.add(file_record)
    await db.commit()
    await db.refresh(file_record)
    return file_record
