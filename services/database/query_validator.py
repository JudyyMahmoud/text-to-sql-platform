"""
Validates LLM-generated SQL before it is ever sent to a live customer
database. This is the single most important security boundary in the
whole platform: the LLM can propose SQL, but this module has final say.
"""
import re

import sqlglot
from sqlglot import exp

from app.config import settings

BLOCKED_KEYWORDS = {
    "DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE",
    "EXEC", "EXECUTE", "CALL", "COPY", "ATTACH", "DETACH",
    "MERGE", "VACUUM", "REINDEX", "CLUSTER",
}

BLOCKED_EXPRESSION_TYPES = (
    exp.Drop, exp.TruncateTable, exp.Alter, exp.Create, exp.Grant,
    exp.Command,
)

# DML that mutates data — allowed only when the resolved table access is
# "read_write" (see core/permissions.py); otherwise always blocked.
MUTATING_EXPRESSION_TYPES = (exp.Insert, exp.Update, exp.Delete)


class SQLValidationResult:
    def __init__(self, is_valid: bool, errors: list[str], normalized_sql: str | None,
                 referenced_tables: list[str], referenced_columns: list[str], query_type: str | None):
        self.is_valid = is_valid
        self.errors = errors
        self.normalized_sql = normalized_sql
        self.referenced_tables = referenced_tables
        self.referenced_columns = referenced_columns
        self.query_type = query_type


def validate_sql(raw_sql: str, dialect: str, allowed_schema: dict) -> SQLValidationResult:
    errors: list[str] = []

    if not raw_sql or not raw_sql.strip():
        return SQLValidationResult(False, ["Empty SQL."], None, [], [], None)

    # --- Block SQL comments outright (a common injection/obfuscation vector) ---
    if "--" in raw_sql or "/*" in raw_sql or "*/" in raw_sql:
        errors.append("SQL comments are not allowed.")

    # --- Block obviously dangerous keywords via regex as a fast first pass ---
    upper_sql = raw_sql.upper()
    for kw in BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", upper_sql):
            errors.append(f"Blocked keyword detected: {kw}")

    # --- Parse with SQLGlot for structural validation ---
    dialect_map = {"postgresql": "postgres", "mysql": "mysql", "sqlserver": "tsql", "oracle": "oracle"}
    sqlglot_dialect = dialect_map.get(dialect, "postgres")

    try:
        statements = sqlglot.parse(raw_sql, read=sqlglot_dialect)
    except Exception as exc:
        errors.append(f"SQL failed to parse: {str(exc)[:200]}")
        return SQLValidationResult(False, errors, None, [], [], None)

    statements = [s for s in statements if s is not None]

    # --- Block multiple statements ---
    if len(statements) != 1:
        errors.append("Only a single SQL statement is allowed per query.")
        return SQLValidationResult(False, errors, None, [], [], None)

    statement = statements[0]

    if isinstance(statement, BLOCKED_EXPRESSION_TYPES):
        errors.append("DDL and administrative statements are not allowed.")

    query_type = "SELECT"
    if isinstance(statement, MUTATING_EXPRESSION_TYPES):
        query_type = type(statement).__name__.upper()

    if not isinstance(statement, (exp.Select, exp.Union, *MUTATING_EXPRESSION_TYPES)):
        if not errors:
            errors.append("Only SELECT/WITH queries (or explicitly permitted DML) are allowed.")

    # --- Extract referenced tables & columns ---
    referenced_tables = sorted({t.name for t in statement.find_all(exp.Table) if t.name})
    referenced_columns = sorted({c.name for c in statement.find_all(exp.Column) if c.name})

    # --- Block references to system schemas / functions regardless of dialect ---
    system_schemas = {"pg_catalog", "information_schema", "sys", "mysql", "performance_schema"}
    for t in statement.find_all(exp.Table):
        if t.db and t.db.lower() in system_schemas:
            errors.append(f"Access to system schema '{t.db}' is not allowed.")

    # --- Enforce table/column allow-list (this is what stops privilege escalation) ---
    for table_name in referenced_tables:
        if table_name not in allowed_schema:
            errors.append(f"Table '{table_name}' is not in your permitted schema.")
            continue
        if query_type != "SELECT" and allowed_schema[table_name]["access"] != "read_write":
            errors.append(f"You do not have write access to table '{table_name}'.")

    allowed_columns = set()
    for t in allowed_schema.values():
        allowed_columns.update(t["columns"])
    for col in referenced_columns:
        # `*` and aggregate aliases are fine; only check real column names we recognise.
        if col == "*":
            continue
        if allowed_columns and col not in allowed_columns and col not in ("*",):
            # Column might belong to a function alias; only flag if it clearly
            # doesn't exist anywhere in the allowed schema.
            errors.append(f"Column '{col}' is not in your permitted schema.")

    # --- Enforce row limit for SELECT statements ---
    normalized_sql = raw_sql.strip().rstrip(";")
    if query_type == "SELECT" and isinstance(statement, exp.Select):
        existing_limit = statement.args.get("limit")
        if existing_limit is None:
            statement = statement.limit(settings.SQL_MAX_ROWS)
        normalized_sql = statement.sql(dialect=sqlglot_dialect)

    is_valid = len(errors) == 0
    return SQLValidationResult(
        is_valid=is_valid,
        errors=errors,
        normalized_sql=normalized_sql if is_valid else None,
        referenced_tables=referenced_tables,
        referenced_columns=referenced_columns,
        query_type=query_type,
    )
