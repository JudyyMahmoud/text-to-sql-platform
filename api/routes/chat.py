import json
import time
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.dependencies import get_current_context
from app.exceptions import NotFoundError
from core.constants import Intent, MessageRole
from core.database import get_db
from core.tenant_context import TenantContext
from models.citation import MessageCitation
from models.conversation import Conversation
from models.message import Message
from models.query_execution import QueryExecution
from schemas.chat import ChatRequest, ChatResponse, CitationInfo, SQLInfo
from agents.graph import run_chat_graph
from agents.state import ChatState

router = APIRouter(tags=["chat"])


async def _get_or_create_conversation(
    db: AsyncSession, ctx: TenantContext, request: ChatRequest
) -> Conversation:
    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == request.conversation_id, Conversation.tenant_id == ctx.tenant_id
            )
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            raise NotFoundError("Conversation not found.")
        return conv

    conv = Conversation(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        title=request.message[:80],
        active_connection_ids=[str(i) for i in request.database_connection_ids],
        active_knowledge_base_ids=[str(i) for i in request.knowledge_base_ids],
    )
    db.add(conv)
    await db.flush()
    return conv


async def _recent_history_text(db: AsyncSession, conversation_id: UUID, limit: int = 6) -> str:
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.desc()).limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return "\n".join(f"{m.role}: {m.content}" for m in messages)


async def _run_pipeline(db: AsyncSession, ctx: TenantContext, request: ChatRequest) -> dict:
    conv = await _get_or_create_conversation(db, ctx, request)

    connection_ids = request.database_connection_ids or [UUID(i) for i in conv.active_connection_ids]
    knowledge_base_ids = request.knowledge_base_ids or [UUID(i) for i in conv.active_knowledge_base_ids]

    history_text = await _recent_history_text(db, conv.id)

    user_message = Message(
        tenant_id=ctx.tenant_id,
        conversation_id=conv.id,
        role=MessageRole.USER,
        content=request.message,
        selected_sources=[str(i) for i in connection_ids] + [str(i) for i in knowledge_base_ids],
    )
    db.add(user_message)
    await db.flush()

    started = time.time()
    initial_state: ChatState = {
        "tenant_id": ctx.tenant_id,
        "user_id": ctx.user_id,
        "is_tenant_admin": ctx.is_tenant_admin,
        "role_ids": ctx.role_ids,
        "question": request.message,
        "conversation_history": history_text,
        "database_connection_ids": connection_ids,
        "knowledge_base_ids": knowledge_base_ids,
    }
    result_state = await run_chat_graph(db, ctx, initial_state)
    latency_ms = int((time.time() - started) * 1000)

    answer = result_state.get("final_answer", "")
    intent = result_state.get("intent", Intent.GENERAL)
    sources_used = result_state.get("sources_used", [])
    sql_results = result_state.get("sql_results") or []
    document_evidence = result_state.get("document_evidence") or []

    assistant_message = Message(
        tenant_id=ctx.tenant_id,
        conversation_id=conv.id,
        parent_message_id=user_message.id,
        role=MessageRole.ASSISTANT,
        content=answer,
        detected_intent=intent,
        selected_sources=sources_used,
        model_name=None,
        latency_ms=latency_ms,
        status="completed",
    )
    db.add(assistant_message)
    await db.flush()

    # --- persist query execution records + citations for full traceability ---
    sql_info: SQLInfo | None = None
    citations: list[CitationInfo] = []

    for sql_result in sql_results:
        qe = QueryExecution(
            tenant_id=ctx.tenant_id,
            conversation_id=conv.id,
            message_id=assistant_message.id,
            connection_id=UUID(sql_result["connection_id"]),
            generated_sql=sql_result.get("sql") or "",
            normalized_sql=sql_result.get("sql"),
            query_type="SELECT",
            validation_status="rejected" if sql_result.get("validation_errors") else "valid",
            validation_errors=sql_result.get("validation_errors", []),
            referenced_tables=sql_result.get("referenced_tables", []),
            referenced_columns=sql_result.get("referenced_columns", []),
            execution_status=sql_result.get("status"),
            execution_time_ms=sql_result.get("execution_time_ms"),
            returned_row_count=sql_result.get("row_count"),
            result_preview=sql_result.get("rows", [])[:20],
            error_message=sql_result.get("error"),
        )
        db.add(qe)
        await db.flush()

        if sql_result.get("status") == "success" and sql_info is None:
            sql_info = SQLInfo(query_execution_id=qe.id, query=sql_result.get("sql"), row_count=sql_result.get("row_count"))

        db.add(
            MessageCitation(
                tenant_id=ctx.tenant_id,
                message_id=assistant_message.id,
                citation_type="database",
                query_execution_id=qe.id,
                title=sql_result.get("connection_name"),
                source_reference=", ".join(sql_result.get("referenced_tables", [])),
            )
        )
        citations.append(CitationInfo(type="database", table=", ".join(sql_result.get("referenced_tables", []))))

    for evidence in document_evidence:
        db.add(
            MessageCitation(
                tenant_id=ctx.tenant_id,
                message_id=assistant_message.id,
                citation_type="document",
                file_id=evidence["file_id"],
                chunk_id=evidence["chunk_id"],
                title=evidence["file_name"],
                page_number=evidence.get("page_number"),
            )
        )
        citations.append(
            CitationInfo(type="document", file_name=evidence["file_name"], page=evidence.get("page_number"))
        )

    conv.last_message_at = assistant_message.created_at
    await db.commit()

    return {
        "message_id": assistant_message.id,
        "conversation_id": conv.id,
        "answer": answer,
        "intent": intent,
        "sources_used": sources_used,
        "sql": sql_info,
        "citations": citations,
    }


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)
):
    result = await _run_pipeline(db, ctx, request)
    return ChatResponse(**result)


@router.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)
):
    """
    Server-Sent Events endpoint. The orchestrator runs to completion first
    (SQL execution and document retrieval are not incremental), then the
    final answer is streamed to the client in small text chunks so the UI
    can render it progressively, followed by a final event with citations.
    """
    result = await _run_pipeline(db, ctx, request)

    async def event_generator():
        answer = result["answer"]
        chunk_size = 40
        for i in range(0, len(answer), chunk_size):
            yield {"event": "token", "data": answer[i : i + chunk_size]}
        final_payload = {
            "message_id": str(result["message_id"]),
            "conversation_id": str(result["conversation_id"]),
            "intent": result["intent"],
            "sources_used": result["sources_used"],
            "sql": result["sql"].model_dump() if result["sql"] else None,
            "citations": [c.model_dump() for c in result["citations"]],
        }
        yield {"event": "done", "data": json.dumps(final_payload)}

    return EventSourceResponse(event_generator())


@router.get("/api/messages/{message_id}/citations")
async def get_message_citations(
    message_id: UUID, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(MessageCitation).where(MessageCitation.message_id == message_id, MessageCitation.tenant_id == ctx.tenant_id)
    )
    citations = result.scalars().all()
    return [
        {
            "id": c.id,
            "type": c.citation_type,
            "title": c.title,
            "page_number": c.page_number,
            "source_reference": c.source_reference,
        }
        for c in citations
    ]


@router.get("/api/messages/{message_id}/sql")
async def get_message_sql(
    message_id: UUID, ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(QueryExecution).where(QueryExecution.message_id == message_id, QueryExecution.tenant_id == ctx.tenant_id)
    )
    executions = result.scalars().all()
    return [
        {
            "id": e.id,
            "connection_id": e.connection_id,
            "generated_sql": e.generated_sql,
            "validation_status": e.validation_status,
            "execution_status": e.execution_status,
            "returned_row_count": e.returned_row_count,
            "execution_time_ms": e.execution_time_ms,
            "error_message": e.error_message,
        }
        for e in executions
    ]
