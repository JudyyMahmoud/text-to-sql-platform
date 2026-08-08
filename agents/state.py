from typing import TypedDict
from uuid import UUID


class ChatState(TypedDict, total=False):
    # --- inputs ---
    tenant_id: UUID
    user_id: UUID
    is_tenant_admin: bool
    role_ids: list[UUID]
    question: str
    conversation_history: str
    database_connection_ids: list[UUID]
    knowledge_base_ids: list[UUID]

    # --- working state ---
    intent: str
    sql_results: list[dict]          # one entry per connection queried
    query_execution_records: list[dict]
    document_evidence: list[dict]

    # --- outputs ---
    final_answer: str
    sources_used: list[str]
