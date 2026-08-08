import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.config import settings  # noqa: E402
from core.database import AsyncSessionLocal  # noqa: E402
from core.security import hash_password  # noqa: E402
from models.role import Role, UserRole  # noqa: E402
from models.tenant import Tenant  # noqa: E402
from models.user import User  # noqa: E402


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.code == settings.DEFAULT_TENANT_CODE))
        tenant = result.scalar_one_or_none()
        if tenant is not None:
            print(f"Default tenant '{settings.DEFAULT_TENANT_CODE}' already exists. Skipping seed.")
            return

        tenant = Tenant(name=settings.DEFAULT_TENANT_NAME, code=settings.DEFAULT_TENANT_CODE)
        db.add(tenant)
        await db.flush()

        admin_role = Role(tenant_id=tenant.id, name="tenant_admin", description="Full tenant administrator")
        db.add(admin_role)
        await db.flush()

        user = User(
            tenant_id=tenant.id,
            email=settings.DEFAULT_ADMIN_EMAIL,
            full_name="Default Admin",
            password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            is_tenant_admin=True,
        )
        db.add(user)
        await db.flush()
        db.add(UserRole(user_id=user.id, role_id=admin_role.id))
        await db.commit()

        print("=" * 60)
        print("Seeded a default tenant and admin user:")
        print(f"  tenant_code : {settings.DEFAULT_TENANT_CODE}")
        print(f"  email       : {settings.DEFAULT_ADMIN_EMAIL}")
        print(f"  password    : {settings.DEFAULT_ADMIN_PASSWORD}")
        print("  (change this password after first login in a real deployment)")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
