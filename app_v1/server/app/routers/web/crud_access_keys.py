from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AccessKey, get_db
from app.models import CrudDeleteRequest, CrudDeleteResponse, CrudListRequest, CrudListResponse, UserData
from app.routers.web.crud_auth import require_crud_user
from app.state import runtime
from app.user_auth.db import AuthAudit
from app.utils.crud import CrudSpec, delete_rows, get_row, list_rows


async def revoke_access_keys(db: AsyncSession, spec: CrudSpec, ids: list[str], owner_clause: object | None) -> int:
    clauses = [spec.model.id.in_(ids)]
    if owner_clause is not None:
        clauses.append(owner_clause)
    rows = (await db.execute(select(spec.model).where(*clauses))).scalars().all()
    now = datetime.now(timezone.utc)
    for row in rows:
        row.status = "revoked"
        row.revoked_at = row.revoked_at or now
        db.add(
            AuthAudit(
                user_id=str(row.user_id),
                event="token_revoked",
                details={"access_key_id": str(row.id), "key_prefix": row.key_prefix},
            )
        )
    await db.commit()
    for row in rows:
        await runtime.close_launchers_for_access_key(str(row.id))
    return len(rows)


CRUD_SPEC = CrudSpec(
    model=AccessKey,
    public_fields=(
        "id",
        "user_id",
        "key_type",
        "name",
        "key_prefix",
        "scopes",
        "status",
        "rate_limit_per_minute",
        "allowed_ips",
        "allowed_origins",
        "last_used_at",
        "expires_at",
        "created_at",
        "revoked_at",
    ),
    searchable_fields=("key_type", "name", "key_prefix", "status", "scopes"),
    sortable_fields=("key_type", "name", "status", "last_used_at", "expires_at", "created_at", "revoked_at"),
    delete_handler=revoke_access_keys,
    allow_owner_delete=True,
)

router = APIRouter(prefix="/access_keys", tags=["crud-access-keys"])


@router.post("/list", response_model=CrudListResponse)
async def api_list_access_keys(
    request: CrudListRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_crud_user),
) -> CrudListResponse:
    return await list_rows(db, CRUD_SPEC, request, current_user)


@router.get("/{row_id}", response_model=dict[str, Any])
async def api_get_access_key(
    row_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_crud_user),
) -> dict[str, Any]:
    return await get_row(db, CRUD_SPEC, row_id, current_user)


@router.post("/delete", response_model=CrudDeleteResponse)
async def api_delete_access_keys(
    request: CrudDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_crud_user),
) -> CrudDeleteResponse:
    return await delete_rows(db, CRUD_SPEC, request, current_user)
