from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import require_tenant_admin
from app.exceptions import AppError
from core.database import get_db
from core.tenant_context import TenantContext
from models.table_permission import ColumnPermission, TablePermission

router = APIRouter(prefix="/api/permissions", tags=["permissions"])


class GrantTablePermissionRequest(BaseModel):
    connection_id: UUID
    table_id: UUID
    role_id: UUID | None = None
    user_id: UUID | None = None
    can_read: bool = True
    can_insert: bool = False
    can_update: bool = False
    can_delete: bool = False
    row_filter: dict = Field(default_factory=dict)
    allowed_column_ids: list[UUID] | None = None  # None = all non-sensitive columns


class TablePermissionResponse(BaseModel):
    id: UUID
    connection_id: UUID
    table_id: UUID
    role_id: UUID | None
    user_id: UUID | None
    can_read: bool
    can_insert: bool
    can_update: bool
    can_delete: bool
    row_filter: dict

    class Config:
        from_attributes = True


@router.post("/table-permissions", response_model=TablePermissionResponse, status_code=201)
async def grant_table_permission(
    payload: GrantTablePermissionRequest,
    ctx: TenantContext = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_db),
):
    """Only tenant administrators may grant table/column/row access — this is the control plane for RBAC."""
    if not payload.role_id and not payload.user_id:
        raise AppError("Either role_id or user_id must be provided.")
    if payload.role_id and payload.user_id:
        raise AppError("Provide only one of role_id or user_id, not both.")

    perm = TablePermission(
        tenant_id=ctx.tenant_id,
        role_id=payload.role_id,
        user_id=payload.user_id,
        connection_id=payload.connection_id,
        table_id=payload.table_id,
        can_read=payload.can_read,
        can_insert=payload.can_insert,
        can_update=payload.can_update,
        can_delete=payload.can_delete,
        row_filter=payload.row_filter,
    )
    db.add(perm)
    await db.flush()

    if payload.allowed_column_ids:
        for column_id in payload.allowed_column_ids:
            db.add(ColumnPermission(table_permission_id=perm.id, column_id=column_id))

    await db.commit()
    await db.refresh(perm)
    return TablePermissionResponse.model_validate(perm)


@router.get("/table-permissions", response_model=list[TablePermissionResponse])
async def list_table_permissions(
    connection_id: UUID | None = None,
    ctx: TenantContext = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(TablePermission).where(TablePermission.tenant_id == ctx.tenant_id)
    if connection_id:
        query = query.where(TablePermission.connection_id == connection_id)
    result = await db.execute(query)
    return [TablePermissionResponse.model_validate(p) for p in result.scalars().all()]


@router.delete("/table-permissions/{permission_id}", status_code=204)
async def revoke_table_permission(
    permission_id: UUID, ctx: TenantContext = Depends(require_tenant_admin), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TablePermission).where(TablePermission.id == permission_id, TablePermission.tenant_id == ctx.tenant_id)
    )
    perm = result.scalar_one_or_none()
    if perm:
        await db.delete(perm)
        await db.commit()
