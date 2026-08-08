class Intent:
    GENERAL = "general"
    DATABASE = "database"
    DOCUMENT = "document"
    HYBRID = "hybrid"
    CLARIFICATION = "clarification"


class MessageRole:
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConnectionStatus:
    PENDING = "pending"
    CONNECTED = "connected"
    FAILED = "failed"


class SchemaSyncStatus:
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"


class ProcessingStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationStatus:
    VALID = "valid"
    REJECTED = "rejected"


class ExecutionStatus:
    SUCCESS = "success"
    FAILED = "failed"


# Database dialects the platform can connect to. postgresql and mysql have
# fully working drivers installed by default; others use the generic
# SQLAlchemy adapter and just need the right driver installed to work.
SUPPORTED_DB_TYPES = ["postgresql", "mysql", "sqlserver", "oracle"]

DEFAULT_ROLE_ADMIN = "tenant_admin"
DEFAULT_ROLE_MEMBER = "member"
