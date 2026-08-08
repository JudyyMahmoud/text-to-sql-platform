from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_context
from app.exceptions import NotFoundError
from core.database import get_db
from core.tenant_context import TenantContext
from models.conversation import Conversation
from schemas.chat import ConversationCreate, ConversationResponse

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    payload: ConversationCreate, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)
):
    conv = Conversation(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        title=payload.title,
        active_connection_ids=[str(i) for i in payload.database_connection_ids],
        active_knowledge_base_ids=[str(i) for i in payload.knowledge_base_ids],
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationResponse.model_validate(conv)


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.tenant_id == ctx.tenant_id, Conversation.user_id == ctx.user_id)
        .order_by(Conversation.created_at.desc())
    )
    return [ConversationResponse.model_validate(c) for c in result.scalars().all()]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.tenant_id == ctx.tenant_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise NotFoundError("Conversation not found.")
    return ConversationResponse.model_validate(conv)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.tenant_id == ctx.tenant_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise NotFoundError("Conversation not found.")
    await db.delete(conv)
    await db.commit()
