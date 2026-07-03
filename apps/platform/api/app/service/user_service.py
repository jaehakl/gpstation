from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import UserAdminUpdate, UserData
from user_auth.db import User


ALLOWED_USER_ROLES = {"admin", "user", "unauthorized"}


NON_NULL_USER_FIELDS = {
    "role",
    "status",
    "credit_balance",
    "credit_pending",
    "credit_withdrawable",
    "trust_score",
    "trust_tier",
    "success_job_count",
    "failed_job_count",
    "disputed_job_count",
    "metadata_json",
}


def user_to_data(user: User) -> UserData:
    role = user.role or "unauthorized"
    return UserData(
        id=str(user.id),
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        password_hash=user.password_hash,
        role=role,
        status=user.status,
        is_active=user.status == "active",
        credit_balance=user.credit_balance,
        credit_pending=user.credit_pending,
        credit_withdrawable=user.credit_withdrawable,
        trust_score=user.trust_score,
        trust_tier=user.trust_tier,
        success_job_count=user.success_job_count,
        failed_job_count=user.failed_job_count,
        disputed_job_count=user.disputed_job_count,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        metadata_json=user.metadata_json or {},
        roles=[role],
    )


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
