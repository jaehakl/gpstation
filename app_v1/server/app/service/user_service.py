from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.settings import settings
from app.user_auth.db import User


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
