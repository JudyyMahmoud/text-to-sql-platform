from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_context
from app.exceptions import NotFoundError
from core.database import get_db
from core.tenant_context import TenantContext
from models.file import File
from models.knowledge_base import KnowledgeBase
from schemas.file import FileResponse, KnowledgeBaseCreate, KnowledgeBaseResponse

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])


@router.post("", response_model=KnowledgeBaseResponse, status_code=201)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)
):
    from app.config import settings

    kb = KnowledgeBase(
        tenant_id=ctx.tenant_id,
        created_by=ctx.user_id,
        name=payload.name,
        description=payload.description,
        embedding_model=settings.EMBEDDING_MODEL,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return KnowledgeBaseResponse.model_validate(kb)


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.tenant_id == ctx.tenant_id))
    return [KnowledgeBaseResponse.model_validate(kb) for kb in result.scalars().all()]


@router.get("/{kb_id}/files", response_model=list[FileResponse])
async def list_knowledge_base_files(
    kb_id: UUID, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.tenant_id == ctx.tenant_id)
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundError("Knowledge base not found.")

    files_result = await db.execute(
        select(File).where(File.knowledge_base_id == kb_id, File.tenant_id == ctx.tenant_id)
    )
    return [FileResponse.model_validate(f) for f in files_result.scalars().all()]
