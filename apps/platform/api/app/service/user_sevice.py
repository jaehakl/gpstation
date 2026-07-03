from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import UserData
from user_auth.db import User


def _to_user_data(user: User) -> UserData:
    role = user.role or "user"
    return UserData(
        id=user.id,
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        role=role,
        status=user.status,
        is_active=user.status == "active",
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        roles=[role],
    )


class UserService:
    @staticmethod
    async def get_users(
        limit: int | None,
        offset: int | None,
        db: AsyncSession,
        user_id: str,
    ) -> list[UserData]:
        stmt = select(User)
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        users = (await db.execute(stmt)).scalars().all()
        return [_to_user_data(user) for user in users]

    @staticmethod
    async def delete_user(id: str, db: AsyncSession, user_id: str) -> bool:
        user = (await db.execute(select(User).where(User.id == id))).scalars().first()
        if not user:
            return False

        await db.delete(user)
        await db.commit()
        return True

    async def get_user_summary(
        who: str,
        db: AsyncSession,
        user_id: str,
    ) -> Optional[UserData]:
        id_to_get = user_id if who == "me" else who
        user = (await db.execute(select(User).where(User.id == id_to_get))).scalar_one_or_none()
        if not user:
            return None

        return _to_user_data(user)
