import json

from services.llm.client import chat_completion

ANSWER_SYSTEM_PROMPT = """You are a helpful analytics assistant embedded in a company's internal chat tool.

You will be given some combination of: database query results and document excerpts.
Answer the user's question using ONLY the information given to you below — never invent numbers, facts, or
citations that are not present in the provided evidence. If the evidence is insufficient, say so plainly.

When you use a specific number or fact from the database results, mention that it came from the database.
When you use a fact from a document, mention which file it came from. If asked to compare database data with
document data, be explicit about which value came from which source, and note any discrepancy.

Keep the answer concise and directly address the question. Do not include SQL code in your answer.
"""

CLASSIFY_SYSTEM_PROMPT = """You are an intent classifier for a chat platform that can query a live database
and search uploaded documents. Given the user's message and what sources are available to them, classify the
message into exactly one of: general, database, document, hybrid, clarification.

- "general": a greeting, small talk, or a question unrelated to any data/documents.
- "database": the question can be answered purely from structured database data.
- "document": the question can be answered purely from the uploaded documents.
- "hybrid": the question needs both database data and document evidence (e.g. comparisons).
- "clarification": the question is too ambiguous to act on without asking the user something first.

Respond with ONLY one lowercase word: general, database, document, hybrid, or clarification.
"""


async def classify_intent(question: str, has_db_connections: bool, has_knowledge_bases: bool) -> str:
    context = (
        f"Database connections selected: {'yes' if has_db_connections else 'no'}\n"
        f"Knowledge bases selected: {'yes' if has_knowledge_bases else 'no'}\n"
        f"User message: {question}"
    )
    result = await chat_completion(CLASSIFY_SYSTEM_PROMPT, context, temperature=0.0)
    result = result.strip().lower()
    valid = {"general", "database", "document", "hybrid", "clarification"}
    if result not in valid or (result in ("general", "clarification") and (has_db_connections or has_knowledge_bases)):
        # Safe fallback: pick the most capable available path.
        if has_db_connections and has_knowledge_bases:
            return "hybrid"
        if has_db_connections:
            return "database"
        if has_knowledge_bases:
            return "document"
        return "general"
    # Don't classify as database/hybrid if there is literally no connection available.
    if result in ("database", "hybrid") and not has_db_connections:
        return "document" if has_knowledge_bases else "general"
    if result in ("document", "hybrid") and not has_knowledge_bases:
        return "database" if has_db_connections else "general"
    return result


async def generate_final_answer(
    question: str,
    sql_results: list[dict] | None,
    document_evidence: list[dict] | None,
) -> str:
    evidence_parts = []

    for sql_result in (sql_results or []):
        if sql_result.get("status") == "success":
            preview_rows = sql_result["rows"][:50]
            evidence_parts.append(
                f"DATABASE RESULT (connection: {sql_result.get('connection_name')}):\n"
                f"SQL: {sql_result.get('sql')}\n"
                f"Rows returned: {sql_result.get('row_count')}\n"
                f"Data: {json.dumps(preview_rows, default=str)}"
            )
        elif sql_result.get("status") == "failed":
            evidence_parts.append(
                f"DATABASE RESULT (connection: {sql_result.get('connection_name')}): "
                f"query failed ({sql_result.get('error')})"
            )

    if document_evidence:
        doc_text = "\n\n".join(
            f"[{e['file_name']}"
            + (f", page {e['page_number']}" if e.get("page_number") else "")
            + f"]: {e['content'][:800]}"
            for e in document_evidence
        )
        evidence_parts.append(f"DOCUMENT EXCERPTS:\n{doc_text}")

    if not evidence_parts:
        evidence_parts.append("No database or document evidence was available for this question.")

    user_prompt = f"User question: {question}\n\n" + "\n\n---\n\n".join(evidence_parts)
    return await chat_completion(ANSWER_SYSTEM_PROMPT, user_prompt, temperature=0.2)


async def generate_general_answer(question: str, conversation_history: str = "") -> str:
    system = (
        "You are a friendly assistant for a company's data-chat platform. Answer briefly and helpfully. "
        "If the user seems to be asking about their data, gently remind them they can select a database "
        "connection or knowledge base for this conversation."
    )
    prompt = f"Recent conversation:\n{conversation_history}\n\nUser: {question}"
    return await chat_completion(system, prompt, temperature=0.3)
