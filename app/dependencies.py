from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import PermissionDeniedError, UnauthorizedError
from core.database import get_db
from core.security import decode_token
from core.tenant_context import TenantContext
from models.user import User
from models.role import UserRole

bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """
    Extracts and validates the bearer JWT, then loads a TenantContext that
    every downstream service/repository call must use to scope data access.
    """
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing bearer token")
    token = credentials.credentials
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise UnauthorizedError("Wrong token type; use an access token")

    user_id = UUID(payload["sub"])
    tenant_id = UUID(payload["tenant_id"])

    # Confirm the user still exists, is active, and truly belongs to this tenant.
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id, User.status == "active")
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("User is no longer active or does not belong to this tenant")

    role_result = await db.execute(select(UserRole.role_id).where(UserRole.user_id == user_id))
    role_ids = [row[0] for row in role_result.all()]

    return TenantContext(
        user_id=user.id,
        tenant_id=user.tenant_id,
        is_tenant_admin=user.is_tenant_admin,
        role_ids=role_ids,
    )


async def require_tenant_admin(ctx: TenantContext = Depends(get_current_context)) -> TenantContext:
    if not ctx.is_tenant_admin:
        raise PermissionDeniedError("This action requires tenant administrator privileges")
    return ctx
