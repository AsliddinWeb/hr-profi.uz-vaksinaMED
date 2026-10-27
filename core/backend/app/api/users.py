from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import plans
from app.db import get_session
from app.deps import AuthContext, error, require, require_any
from app.models.auth import Role, User
from app.rbac import SUPERUSER_ROLE, covers
from app.security import (
    generate_temp_password,
    hash_password,
    validate_password_strength,
)
from app.services import auth as svc
from app.services.audit import audit
from app.services.logins import unique_login
from app.services.notifications import deliver, notify

router = APIRouter(prefix="/v1/users", tags=["users"])


class UserOut(BaseModel):
    id: int
    login: str
    full_name: str
    phone: str | None
    role_key: str
    role_name_uz: str
    role_name_ru: str
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime


def to_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        login=u.login,
        full_name=u.full_name,
        phone=u.phone,
        role_key=u.role.key,
        role_name_uz=u.role.name_uz,
        role_name_ru=u.role.name_ru,
        is_active=u.is_active,
        must_change_password=u.must_change_password,
        last_login_at=u.last_login_at,
        created_at=u.created_at,
    )


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    role_key: str
    phone: str | None = Field(default=None, max_length=32)
    login: str | None = Field(default=None, pattern=r"^[a-z0-9._-]{3,64}$")
    password: str | None = Field(default=None, max_length=256)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    role_key: str | None = None


class Page(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    size: int


async def _role(db: AsyncSession, key: str) -> Role:
    role = await db.scalar(select(Role).where(Role.key == key))
    if not role:
        raise error(400, "unknown_role")
    return role


def _check_can_assign(auth: AuthContext, role: Role) -> None:
    """Privilege escalation: o'zingizdan yuqori huquqli rolni bera olmaysiz."""
    if not covers(auth.permissions, role.permission_keys):
        raise error(403, "cannot_assign_role", role=role.key)


def _check_can_manage(auth: AuthContext, target: User) -> None:
    if not covers(auth.permissions, target.role.permission_keys):
        raise error(403, "cannot_manage_user")


async def last_superuser_guard(db: AsyncSession, target: User) -> None:
    """Tizimda kamida bitta faol Ta'sischi qolishi shart."""
    if target.role.key != SUPERUSER_ROLE or not target.is_active:
        return
    others = await db.scalar(
        select(func.count())
        .select_from(User)
        .join(Role)
        .where(Role.key == SUPERUSER_ROLE, User.is_active.is_(True), User.id != target.id)
    )
    if not others:
        raise error(409, "last_superuser")


async def _get(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise error(404, "not_found")
    return user


@router.get("/assignable-roles")
async def assignable_roles(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require_any("users.read", "users.create", "users.update")),
):
    """Rollar ro'yxati (roles.read talab qilinmaydi). `assignable`: shu rolni berish huquqingiz bor."""
    roles = (await db.scalars(select(Role).order_by(Role.id))).all()
    return [
        {
            "key": r.key,
            "name_uz": r.name_uz,
            "name_ru": r.name_ru,
            "assignable": covers(auth.permissions, r.permission_keys),
        }
        for r in roles
    ]


@router.get("", response_model=Page)
async def list_users(
    q: str | None = None,
    role: str | None = None,
    active: bool | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("users.read")),
):
    stmt = select(User).join(Role)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(User.full_name.ilike(like), User.login.ilike(like), User.phone.ilike(like))
        )
    if role:
        stmt = stmt.where(Role.key == role)
    if active is not None:
        stmt = stmt.where(User.is_active.is_(active))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(User.full_name).offset((page - 1) * size).limit(size)
        )
    ).unique().all()
    return Page(items=[to_out(u) for u in rows], total=total or 0, page=page, size=size)


@router.post("", status_code=201)
async def create_user(
    body: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("users.create")),
):
    role = await _role(db, body.role_key)
    _check_can_assign(auth, role)
    await plans.ensure_seat(db)

    login = body.login or await unique_login(db, body.full_name)
    if await db.scalar(select(User.id).where(User.login == login)):
        raise error(409, "login_taken")

    generated = body.password is None
    password = body.password or generate_temp_password()
    if not generated:
        problem = validate_password_strength(password, login)
        if problem:
            raise error(400, problem)

    user = User(
        login=login,
        password_hash=hash_password(password),
        full_name=body.full_name.strip(),
        phone=body.phone,
        role_id=role.id,
        must_change_password=True,  # birinchi kirishda foydalanuvchi o'zi parol qo'yadi
    )
    db.add(user)
    await db.flush()
    await audit(
        db, request, "user.create", actor=auth.user, entity="user", entity_id=user.id,
        data={"login": login, "role": role.key},
    )  # fmt: skip
    await db.commit()
    await db.refresh(user)
    return {"user": to_out(user), "temp_password": password if generated else None}


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("users.read")),
):
    return to_out(await _get(db, user_id))


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("users.update")),
):
    user = await _get(db, user_id)
    _check_can_manage(auth, user)
    changes: dict = {}
    notes: list = []

    if body.full_name is not None:
        user.full_name = body.full_name.strip()
        changes["full_name"] = user.full_name
    if body.phone is not None:
        user.phone = body.phone or None
        changes["phone"] = user.phone
    if body.role_key is not None and body.role_key != user.role.key:
        new_role = await _role(db, body.role_key)
        _check_can_assign(auth, new_role)
        await last_superuser_guard(db, user)
        changes["role"] = {"from": user.role.key, "to": new_role.key}
        user.role = new_role
        user.role_id = new_role.id
        notes = await notify(
            db, [user.id], "account.role_changed",
            params={"role_uz": new_role.name_uz, "role_ru": new_role.name_ru},
        )  # fmt: skip
        # Rol o'zgarsa ruxsatlar o'zgaradi: eski sessiyalar yopiladi
        await svc.revoke_user_sessions(db, user.id)

    if changes:
        await audit(db, request, "user.update", actor=auth.user, entity="user",
                    entity_id=user.id, data=changes)  # fmt: skip
        await db.commit()
        await db.refresh(user)
        await deliver(request.app, notes)
    return to_out(user)


async def _set_active(
    user_id: int, active: bool, request: Request, db: AsyncSession, auth: AuthContext
) -> UserOut:
    user = await _get(db, user_id)
    _check_can_manage(auth, user)
    if not active:
        if user.id == auth.user.id:
            raise error(409, "cannot_deactivate_self")
        await last_superuser_guard(db, user)
    if user.is_active != active:
        if active:
            await plans.ensure_seat(db)
        user.is_active = active
        if not active:
            await svc.revoke_user_sessions(db, user.id)
        await audit(db, request, "user.activate" if active else "user.deactivate",
                    actor=auth.user, entity="user", entity_id=user.id)  # fmt: skip
        await db.commit()
    return to_out(user)


@router.post("/{user_id}/deactivate", response_model=UserOut)
async def deactivate(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("users.deactivate")),
):
    return await _set_active(user_id, False, request, db, auth)


@router.post("/{user_id}/activate", response_model=UserOut)
async def activate(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("users.deactivate")),
):
    return await _set_active(user_id, True, request, db, auth)


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("users.reset_password")),
):
    user = await _get(db, user_id)
    _check_can_manage(auth, user)
    password = generate_temp_password()
    user.password_hash = hash_password(password)
    user.must_change_password = True
    await svc.revoke_user_sessions(db, user.id)
    await audit(db, request, "user.reset_password", actor=auth.user, entity="user",
                entity_id=user.id)  # fmt: skip
    await db.commit()
    return {"temp_password": password}


@router.post("/{user_id}/revoke-sessions", status_code=204)
async def revoke_sessions(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("sessions.manage")),
):
    user = await _get(db, user_id)
    _check_can_manage(auth, user)
    await svc.revoke_user_sessions(db, user.id)
    await audit(db, request, "user.revoke_sessions", actor=auth.user, entity="user",
                entity_id=user.id)  # fmt: skip
    await db.commit()
