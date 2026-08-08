from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterTenantRequest(BaseModel):
    tenant_name: str = Field(..., min_length=2, max_length=200)
    tenant_code: str = Field(..., min_length=2, max_length=100)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8)
    admin_full_name: str | None = None


class LoginRequest(BaseModel):
    tenant_code: str
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    full_name: str | None
    is_tenant_admin: bool

    class Config:
        from_attributes = True
