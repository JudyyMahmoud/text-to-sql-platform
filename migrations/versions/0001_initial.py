"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 384  # matches BAAI/bge-small-en-v1.5, the default local embedding model


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("password_hash", sa.Text),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("is_tenant_admin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("idx_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )
    op.create_index("idx_roles_tenant_id", "roles", ["tenant_id"])

    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "database_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("database_type", sa.String(50), nullable=False),
        sa.Column("host", sa.String(255)),
        sa.Column("port", sa.Integer),
        sa.Column("database_name", sa.String(255)),
        sa.Column("username", sa.String(255)),
        sa.Column("encrypted_password", sa.Text),
        sa.Column("encrypted_connection_string", sa.Text),
        sa.Column("ssl_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("ssl_settings", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("connection_options", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("last_tested_at", sa.DateTime(timezone=True)),
        sa.Column("last_test_message", sa.Text),
        sa.Column("schema_sync_status", sa.String(30), server_default="pending"),
        sa.Column("last_schema_sync_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_database_connection_name"),
    )
    op.create_index("idx_database_connections_tenant", "database_connections", ["tenant_id"])

    op.create_table(
        "database_schemas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schema_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("connection_id", "schema_name", name="uq_database_schema"),
    )
    op.create_index("idx_database_schemas_tenant", "database_schemas", ["tenant_id"])

    op.create_table(
        "database_tables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schema_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("database_schemas.id", ondelete="CASCADE")),
        sa.Column("table_name", sa.String(255), nullable=False),
        sa.Column("table_type", sa.String(50), nullable=False, server_default="table"),
        sa.Column("description", sa.Text),
        sa.Column("estimated_row_count", sa.BigInteger),
        sa.Column("primary_key_columns", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_sensitive", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("connection_id", "schema_id", "table_name", name="uq_database_table"),
    )
    op.create_index("idx_database_tables_tenant", "database_tables", ["tenant_id"])

    op.create_table(
        "database_columns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("column_name", sa.String(255), nullable=False),
        sa.Column("data_type", sa.String(100), nullable=False),
        sa.Column("ordinal_position", sa.Integer),
        sa.Column("is_nullable", sa.Boolean),
        sa.Column("is_primary_key", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_foreign_key", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_sensitive", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("referenced_schema", sa.String(255)),
        sa.Column("referenced_table", sa.String(255)),
        sa.Column("referenced_column", sa.String(255)),
        sa.Column("description", sa.Text),
        sa.Column("sample_values", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("table_id", "column_name", name="uq_database_column"),
    )
    op.create_index("idx_database_columns_tenant", "database_columns", ["tenant_id"])

    op.create_table(
        "table_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("can_read", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("can_insert", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("can_update", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("can_delete", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("row_filter", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "(role_id IS NOT NULL AND user_id IS NULL) OR (role_id IS NULL AND user_id IS NOT NULL)",
            name="chk_permission_subject",
        ),
    )
    op.create_index("idx_table_permissions_tenant", "table_permissions", ["tenant_id"])

    op.create_table(
        "column_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("table_permission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("table_permissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("column_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("database_columns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("can_read", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("can_filter", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("can_aggregate", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("mask_type", sa.String(50)),
        sa.UniqueConstraint("table_permission_id", "column_id", name="uq_column_permission"),
    )

    op.create_table(
        "knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("embedding_model", sa.String(255)),
        sa.Column("chunking_config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_knowledge_base_name"),
    )
    op.create_index("idx_knowledge_bases_tenant", "knowledge_bases", ["tenant_id"])

    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id", ondelete="SET NULL")),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("original_name", sa.String(500), nullable=False),
        sa.Column("stored_name", sa.String(500), nullable=False),
        sa.Column("storage_path", sa.Text, nullable=False),
        sa.Column("mime_type", sa.String(255)),
        sa.Column("extension", sa.String(30)),
        sa.Column("file_size_bytes", sa.BigInteger),
        sa.Column("checksum", sa.String(128)),
        sa.Column("processing_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("processing_error", sa.Text),
        sa.Column("page_count", sa.Integer),
        sa.Column("extracted_text_length", sa.BigInteger),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_files_tenant", "files", ["tenant_id"])

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(128)),
        sa.Column("page_number", sa.Integer),
        sa.Column("section_title", sa.Text),
        sa.Column("token_count", sa.Integer),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("embedding", Vector(EMBEDDING_DIM)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("file_id", "chunk_index", name="uq_document_chunk"),
    )
    op.create_index("idx_document_chunks_tenant", "document_chunks", ["tenant_id"])
    op.execute(
        "CREATE INDEX idx_document_chunks_embedding ON document_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("active_connection_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("active_knowledge_base_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_conversations_tenant", "conversations", ["tenant_id"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("message_type", sa.String(30), nullable=False, server_default="text"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("structured_content", postgresql.JSONB),
        sa.Column("detected_intent", sa.String(50)),
        sa.Column("selected_sources", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("model_name", sa.String(255)),
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("status", sa.String(30), nullable=False, server_default="completed"),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_messages_tenant", "messages", ["tenant_id"])
    op.create_index("idx_messages_conversation", "messages", ["conversation_id"])

    op.create_table(
        "query_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL")),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generated_sql", sa.Text, nullable=False),
        sa.Column("normalized_sql", sa.Text),
        sa.Column("query_type", sa.String(30)),
        sa.Column("validation_status", sa.String(30), nullable=False),
        sa.Column("validation_errors", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("applied_row_filters", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("referenced_tables", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("referenced_columns", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("execution_status", sa.String(30)),
        sa.Column("execution_time_ms", sa.Integer),
        sa.Column("returned_row_count", sa.Integer),
        sa.Column("result_preview", postgresql.JSONB),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_query_executions_tenant", "query_executions", ["tenant_id"])

    op.create_table(
        "message_citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("citation_type", sa.String(30), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_chunks.id", ondelete="SET NULL")),
        sa.Column("query_execution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("query_executions.id", ondelete="SET NULL")),
        sa.Column("title", sa.Text),
        sa.Column("source_reference", sa.Text),
        sa.Column("page_number", sa.Integer),
        sa.Column("relevance_score", sa.Numeric(8, 6)),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_message_citations_tenant", "message_citations", ["tenant_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="SET NULL")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100)),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True)),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("request_id", sa.String(100)),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_audit_logs_tenant", "audit_logs", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("message_citations")
    op.drop_table("query_executions")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("document_chunks")
    op.drop_table("files")
    op.drop_table("knowledge_bases")
    op.drop_table("column_permissions")
    op.drop_table("table_permissions")
    op.drop_table("database_columns")
    op.drop_table("database_tables")
    op.drop_table("database_schemas")
    op.drop_table("database_connections")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
    op.drop_table("tenants")
