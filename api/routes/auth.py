from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_context
from app.exceptions import ConflictError, UnauthorizedError
from core.database import get_db
from core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from core.tenant_context import TenantContext
from models.role import Role, UserRole
from models.tenant import Tenant
from models.user import User
from schemas.auth import LoginRequest, MeResponse, RefreshRequest, RegisterTenantRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register-tenant", response_model=TokenResponse, status_code=201)
async def register_tenant(payload: RegisterTenantRequest, db: AsyncSession = Depends(get_db)):
    """
    Creates a brand new tenant plus its first tenant-administrator user.
    This is how a new customer organization onboards onto the platform.
    """
    existing = await db.execute(select(Tenant).where(Tenant.code == payload.tenant_code))
    if existing.scalar_one_or_none():
        raise ConflictError(f"Tenant code '{payload.tenant_code}' is already taken.")

    tenant = Tenant(name=payload.tenant_name, code=payload.tenant_code)
    db.add(tenant)
    await db.flush()

    admin_role = Role(tenant_id=tenant.id, name="tenant_admin", description="Full tenant administrator")
    db.add(admin_role)
    await db.flush()

    user = User(
        tenant_id=tenant.id,
        email=payload.admin_email,
        full_name=payload.admin_full_name,
        password_hash=hash_password(payload.admin_password),
        is_tenant_admin=True,
    )
    db.add(user)
    await db.flush()

    db.add(UserRole(user_id=user.id, role_id=admin_role.id))
    await db.commit()

    access_token = create_access_token(user.id, tenant.id, True)
    refresh_token = create_refresh_token(user.id, tenant.id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.code == payload.tenant_code, Tenant.status == "active"))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise UnauthorizedError("Invalid tenant, email, or password.")

    result = await db.execute(
        select(User).where(User.tenant_id == tenant.id, User.email == payload.email, User.status == "active")
    )
    user = result.scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Invalid tenant, email, or password.")

    access_token = create_access_token(user.id, tenant.id, user.is_tenant_admin)
    refresh_token = create_refresh_token(user.id, tenant.id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    data = decode_token(payload.refresh_token)
    if data.get("type") != "refresh":
        raise UnauthorizedError("Wrong token type; use a refresh token")

    from uuid import UUID

    user_id = UUID(data["sub"])
    tenant_id = UUID(data["tenant_id"])

    result = await db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant_id))
    user = result.scalar_one_or_none()
    if user is None or user.status != "active":
        raise UnauthorizedError("User is no longer active.")

    access_token = create_access_token(user.id, tenant_id, user.is_tenant_admin)
    new_refresh_token = create_refresh_token(user.id, tenant_id)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=MeResponse)
async def me(ctx: TenantContext = Depends(get_current_context), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == ctx.user_id))
    user = result.scalar_one()
    return MeResponse.model_validate(user)
