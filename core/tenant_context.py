"""
Every authenticated request carries a TenantContext. Every single database
query in the app must be filtered by tenant_id using this context — this is
the core mechanism that keeps tenants isolated from each other.
"""
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TenantContext:
    user_id: UUID
    tenant_id: UUID
    is_tenant_admin: bool
    role_ids: list[UUID]
