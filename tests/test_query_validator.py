import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.database.query_validator import validate_sql

ALLOWED_SCHEMA = {
    "customers": {"table_id": "1", "access": "read", "columns": ["id", "name", "country"], "row_filter": {}},
    "orders": {"table_id": "2", "access": "read_write", "columns": ["id", "customer_id", "amount", "status"], "row_filter": {}},
}


def test_valid_select_is_accepted():
    result = validate_sql("SELECT id, name FROM customers", "postgresql", ALLOWED_SCHEMA)
    assert result.is_valid
    assert "LIMIT" in result.normalized_sql.upper()


def test_drop_table_is_blocked():
    result = validate_sql("DROP TABLE customers", "postgresql", ALLOWED_SCHEMA)
    assert not result.is_valid
    assert any("DROP" in e or "not allowed" in e.lower() for e in result.errors)


def test_multiple_statements_are_blocked():
    result = validate_sql("SELECT * FROM customers; DROP TABLE customers;", "postgresql", ALLOWED_SCHEMA)
    assert not result.is_valid


def test_sql_comments_are_blocked():
    result = validate_sql("SELECT * FROM customers -- steal data", "postgresql", ALLOWED_SCHEMA)
    assert not result.is_valid


def test_unauthorized_table_is_rejected():
    result = validate_sql("SELECT * FROM secret_salaries", "postgresql", ALLOWED_SCHEMA)
    assert not result.is_valid
    assert any("secret_salaries" in e for e in result.errors)


def test_write_without_permission_is_rejected():
    result = validate_sql("DELETE FROM customers WHERE id = 1", "postgresql", ALLOWED_SCHEMA)
    assert not result.is_valid


def test_write_with_permission_is_allowed():
    result = validate_sql("UPDATE orders SET status = 'shipped' WHERE id = 1", "postgresql", ALLOWED_SCHEMA)
    assert result.is_valid


def test_system_schema_is_blocked():
    result = validate_sql("SELECT * FROM pg_catalog.pg_tables", "postgresql", ALLOWED_SCHEMA)
    assert not result.is_valid
