from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserAdminUpdate, UserData
from app.settings import settings
from app.user_auth.db import User

ALLOWED_USER_ROLES = {"admin", "user", "unauthorized"}
NON_NULL_USER_FIELDS = {"role", "status"}


def user_to_data(user: User) -> UserData:
    role = user.role or "unauthorized"
    return UserData(
        id=str(user.id),
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        role=role,
        status=user.status,
        is_active=user.status == "active",
        roles=[role],
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def ensure_static_token_users(db: AsyncSession) -> None:
    seen_user_ids: set[str] = set()
    for token_principal in settings.tokens.values():
        user_id = token_principal.user_id
        if user_id in seen_user_ids:
            continue
        seen_user_ids.add(user_id)

        user = await db.get(User, user_id)
        if user is not None:
            continue

        db.add(
            User(
                id=user_id,
                username=f"static-{user_id[:8]}",
                display_name="Static Demo User",
                role="user",
                status="active",
            )
        )
    await db.commit()


class UserService:
    @staticmethod
    async def list_users(db: AsyncSession, limit: int | None, offset: int | None) -> list[UserData]:
        stmt = select(User).order_by(User.created_at.desc(), User.id.asc())
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        users = (await db.execute(stmt)).scalars().all()
        return [user_to_data(user) for user in users]

    @staticmethod
    async def count_users(db: AsyncSession) -> int:
        return len((await db.execute(select(User.id))).all())

    @staticmethod
    async def get_user(db: AsyncSession, user_id: str) -> User | None:
        return await db.get(User, user_id)

    @staticmethod
    async def update_user(db: AsyncSession, user_id: str, payload: UserAdminUpdate) -> UserData | None:
        user = await UserService.get_user(db, user_id)
        if user is None:
            return None

        data = payload.model_dump(exclude_unset=True)
        for field_name in NON_NULL_USER_FIELDS:
            if field_name in data and data[field_name] is None:
                raise ValueError(f"{field_name} cannot be null")
        role = data.get("role")
        if role is not None and role not in ALLOWED_USER_ROLES:
            raise ValueError("Invalid role")

        for field_name, value in data.items():
            setattr(user, field_name, value)

        await db.commit()
        await db.refresh(user)
        return user_to_data(user)

    @staticmethod
    async def delete_user(db: AsyncSession, user_id: str) -> bool:
        user = await UserService.get_user(db, user_id)
        if user is None:
            return False
        await db.delete(user)
        await db.commit()
        return True
