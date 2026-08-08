import json
import re

from services.llm.client import chat_completion

SQL_SYSTEM_PROMPT = """You are a careful SQL generation engine inside a secure backend.

Rules you MUST follow:
- Only use tables and columns that appear in the ALLOWED SCHEMA given to you. Never invent tables or columns.
- Never write DROP, TRUNCATE, ALTER, CREATE, GRANT, REVOKE, EXEC, CALL, COPY, or any multi-statement SQL.
- Never write SQL comments.
- Prefer simple, correct, read-only SELECT statements unless the user clearly asks to insert/update/delete
  AND the target table's access is "read_write" in the allowed schema.
- Only write ONE SQL statement.
- Respond with ONLY the raw SQL statement — no markdown fences, no explanation, no comments.
- If the question cannot be answered using only the ALLOWED SCHEMA, respond with exactly: NO_QUERY_POSSIBLE
"""


def _format_schema_for_prompt(allowed_schema: dict) -> str:
    lines = []
    for table_name, info in allowed_schema.items():
        cols = ", ".join(info["columns"])
        lines.append(f"- {table_name} (access: {info['access']}): columns [{cols}]")
    return "\n".join(lines) if lines else "(no tables available)"


async def generate_sql(question: str, allowed_schema: dict, dialect: str, conversation_history: str = "") -> str | None:
    if not allowed_schema:
        return None

    schema_text = _format_schema_for_prompt(allowed_schema)
    user_prompt = (
        f"Database dialect: {dialect}\n\n"
        f"ALLOWED SCHEMA (this is the ONLY schema you may use):\n{schema_text}\n\n"
        f"Recent conversation (for context only):\n{conversation_history}\n\n"
        f"User question: {question}\n\n"
        "Write the SQL statement now."
    )
    raw = await chat_completion(SQL_SYSTEM_PROMPT, user_prompt, temperature=0.0)
    raw = raw.strip()

    # Strip markdown fences if the model added them anyway.
    raw = re.sub(r"^```(sql)?", "", raw.strip(), flags=re.IGNORECASE).strip()
    raw = re.sub(r"```$", "", raw.strip()).strip()

    if not raw or raw.upper().startswith("NO_QUERY_POSSIBLE"):
        return None
    return raw
