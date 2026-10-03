"""User management (admin only)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_admin
from app.core.security import hash_password
from app.models import User
from app.models.enums import UserRole
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserOut, UserUpdate

router = APIRouter()


@router.get("", response_model=Page[UserOut])
async def list_users(
    page: int = 1,
    page_size: int = 25,
    db: AsyncSession = Depends(get_db_session),
    _admin: User = Depends(require_admin),
) -> Page[UserOut]:
    stmt = select(User)
    total = (await db.scalars(select(func.count()).select_from(stmt.subquery()))).one()
    users = (
        (await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    ).all()
    return Page(
        items=[UserOut.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db_session),
    _admin: User = Depends(require_admin),
) -> User:
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db_session),
    _admin: User = Depends(require_admin),
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    data = payload.model_dump(exclude_unset=True)
    if "role" in data and data["role"] == UserRole.ADMIN:
        # Guard: at least one active admin must always remain.
        admins = (
            await db.scalars(
                select(func.count())
                .select_from(User)
                .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
            )
        ).one()
        if user.role != UserRole.ADMIN and admins < 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "Debe existir un admin activo")
    for field, value in data.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user
