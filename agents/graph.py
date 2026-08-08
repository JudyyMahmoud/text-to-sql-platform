"""
The chat orchestrator. Built with LangGraph as a small state machine:

    classify -> (database_agent?) -> (document_agent?) -> generate_answer

Rather than one permanent agent per customer table, there is a single
generic "database agent" node that is handed a request-specific,
permission-filtered schema (see core/permissions.py) for whichever
connection(s) are selected in the conversation. This keeps the graph
identical across every tenant and industry.
"""
from uuid import UUID

from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from agents.state import ChatState
from core.constants import Intent
from core.permissions import get_allowed_schema
from core.tenant_context import TenantContext
from services.database.connection_service import get_connection
from services.database.query_executor import execute_sql
from services.database.query_validator import validate_sql
from services.documents.retrieval_service import retrieve_relevant_chunks
from services.llm.answer_generator import classify_intent, generate_final_answer, generate_general_answer
from services.llm.sql_generator import generate_sql


def build_chat_graph(db: AsyncSession, ctx: TenantContext):
    """Builds (and compiles) the LangGraph state machine for a single request."""

    async def classify_node(state: ChatState) -> ChatState:
        intent = await classify_intent(
            state["question"],
            has_db_connections=bool(state["database_connection_ids"]),
            has_knowledge_bases=bool(state["knowledge_base_ids"]),
        )
        state["intent"] = intent
        return state

    async def database_node(state: ChatState) -> ChatState:
        sql_results: list[dict] = []
        for connection_id in state["database_connection_ids"]:
            conn = await get_connection(db, ctx, UUID(str(connection_id)))
            allowed_schema = await get_allowed_schema(db, ctx, conn.id)

            if not allowed_schema:
                sql_results.append(
                    {
                        "connection_id": str(conn.id),
                        "connection_name": conn.name,
                        "status": "failed",
                        "sql": None,
                        "error": "You have no permitted tables on this connection.",
                        "row_count": 0,
                        "rows": [],
                        "validation_errors": [],
                    }
                )
                continue

            raw_sql = await generate_sql(
                state["question"], allowed_schema, conn.database_type, state.get("conversation_history", "")
            )
            if raw_sql is None:
                sql_results.append(
                    {
                        "connection_id": str(conn.id),
                        "connection_name": conn.name,
                        "status": "failed",
                        "sql": None,
                        "error": "Could not translate the question into a query using the permitted schema.",
                        "row_count": 0,
                        "rows": [],
                        "validation_errors": [],
                    }
                )
                continue

            validation = validate_sql(raw_sql, conn.database_type, allowed_schema)
            if not validation.is_valid:
                sql_results.append(
                    {
                        "connection_id": str(conn.id),
                        "connection_name": conn.name,
                        "status": "rejected",
                        "sql": raw_sql,
                        "error": "; ".join(validation.errors),
                        "row_count": 0,
                        "rows": [],
                        "validation_errors": validation.errors,
                    }
                )
                continue

            exec_result = execute_sql(conn, validation.normalized_sql, validation.query_type)
            sql_results.append(
                {
                    "connection_id": str(conn.id),
                    "connection_name": conn.name,
                    "status": exec_result["status"],
                    "sql": validation.normalized_sql,
                    "error": exec_result["error"],
                    "row_count": exec_result["row_count"],
                    "rows": exec_result["rows"],
                    "execution_time_ms": exec_result["execution_time_ms"],
                    "referenced_tables": validation.referenced_tables,
                    "referenced_columns": validation.referenced_columns,
                    "validation_errors": [],
                }
            )
        state["sql_results"] = sql_results
        return state

    async def document_node(state: ChatState) -> ChatState:
        evidence = await retrieve_relevant_chunks(
            db, ctx, state["question"], [UUID(str(k)) for k in state["knowledge_base_ids"]]
        )
        state["document_evidence"] = evidence
        return state

    async def final_answer_node(state: ChatState) -> ChatState:
        intent = state["intent"]
        sources_used: list[str] = []

        if intent == Intent.GENERAL or intent == Intent.CLARIFICATION:
            answer = await generate_general_answer(state["question"], state.get("conversation_history", ""))
            state["final_answer"] = answer
            state["sources_used"] = sources_used
            return state

        sql_results = state.get("sql_results") or []
        document_evidence = state.get("document_evidence") or []

        if any(r.get("status") == "success" for r in sql_results):
            sources_used.append("database")
        if document_evidence:
            sources_used.append("documents")

        answer = await generate_final_answer(state["question"], sql_results, document_evidence)
        state["final_answer"] = answer
        state["sources_used"] = sources_used
        return state

    def route_after_classify(state: ChatState) -> str:
        intent = state["intent"]
        if intent == Intent.DATABASE:
            return "database_agent"
        if intent == Intent.DOCUMENT:
            return "document_agent"
        if intent == Intent.HYBRID:
            return "database_agent"  # hybrid always goes db -> documents -> answer
        return "generate_answer"

    def route_after_database(state: ChatState) -> str:
        if state["intent"] == Intent.HYBRID:
            return "document_agent"
        return "generate_answer"

    graph = StateGraph(ChatState)
    graph.add_node("classify", classify_node)
    graph.add_node("database_agent", database_node)
    graph.add_node("document_agent", document_node)
    graph.add_node("generate_answer", final_answer_node)

    graph.set_entry_point("classify")
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {"database_agent": "database_agent", "document_agent": "document_agent", "generate_answer": "generate_answer"},
    )
    graph.add_conditional_edges(
        "database_agent",
        route_after_database,
        {"document_agent": "document_agent", "generate_answer": "generate_answer"},
    )
    graph.add_edge("document_agent", "generate_answer")
    graph.add_edge("generate_answer", END)

    return graph.compile()


async def run_chat_graph(db: AsyncSession, ctx: TenantContext, initial_state: ChatState) -> ChatState:
    graph = build_chat_graph(db, ctx)
    result = await graph.ainvoke(initial_state)
    return result