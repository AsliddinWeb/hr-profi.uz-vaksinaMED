"""Xodim uchun tizimga kirish hisobini yaratish/ulash."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import plans
from app.deps import AuthContext, error
from app.models.auth import Role, User
from app.models.employees import Employee
from app.rbac import covers
from app.security import generate_temp_password, hash_password
from app.services.logins import unique_login


async def create_account(
    db: AsyncSession, employee: Employee, role_key: str, auth: AuthContext
) -> tuple[User, str]:
    """Yangi User yaratib xodimga ulaydi. (user, vaqtinchalik parol) qaytaradi."""
    if not auth.can("employees.accounts"):
        raise error(403, "forbidden", permission="employees.accounts")
    if employee.user_id is not None:
        raise error(409, "account_exists")
    if employee.status != "active":
        raise error(409, "employee_dismissed")
    role = await db.scalar(select(Role).where(Role.key == role_key))
    if not role:
        raise error(400, "unknown_role")
    if not covers(auth.permissions, role.permission_keys):
        raise error(403, "cannot_assign_role", role=role.key)

    await plans.ensure_seat(db)
    login = await unique_login(db, employee.full_name)
    password = generate_temp_password()
    user = User(
        login=login,
        password_hash=hash_password(password),
        full_name=employee.full_name,
        phone=employee.phone,
        role_id=role.id,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    employee.user_id = user.id
    await db.flush()
    return user, password


async def link_account(db: AsyncSession, employee: Employee, user_id: int) -> User:
    """Mavjud foydalanuvchini xodimga ulaydi (bir foydalanuvchi bitta xodimga)."""
    user = await db.get(User, user_id)
    if not user:
        raise error(400, "unknown_user")
    taken = await db.scalar(
        select(Employee.id).where(Employee.user_id == user_id, Employee.id != employee.id)
    )
    if taken:
        raise error(409, "user_already_linked")
    employee.user_id = user.id
    await db.flush()
    return user
