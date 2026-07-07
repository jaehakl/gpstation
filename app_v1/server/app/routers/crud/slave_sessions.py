from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SlaveSession, get_db
from app.models import UserData
from app.routers.crud.auth import require_crud_user
from app.routers.crud.models import CrudDeleteRequest, CrudDeleteResponse, CrudListRequest, CrudListResponse
from app.service.session_service import SessionService
from app.utils.crud import CrudSpec, delete_rows, get_row, list_rows


async def close_slave_sessions(db: AsyncSession, spec: CrudSpec, ids: list[str], owner_clause: object | None) -> int:
    clauses = [spec.model.id.in_(ids)]
    if owner_clause is not None:
        clauses.append(owner_clause)
    close_ids = (await db.execute(select(spec.model.id).where(and_(*clauses)))).scalars().all()

    deleted = 0
    for row_id in close_ids:
        closed = await SessionService.close_session(db, row_id, "closed by CRUD")
        if closed is not None:
            deleted += 1
    return deleted


CRUD_SPEC = CrudSpec(
    model=SlaveSession,
    public_fields=(
        "id",
        "user_id",
        "launcher_id",
        "slave_app_id",
        "master_ip_address",
        "master_user_agent",
        "status",
        "ttl_seconds",
        "expires_at",
        "ready_at",
        "closed_at",
        "last_error",
        "created_at",
        "updated_at",
    ),
    searchable_fields=("slave_app_id", "master_ip_address", "master_user_agent", "status", "last_error"),
    sortable_fields=("slave_app_id", "status", "ttl_seconds", "expires_at", "ready_at", "closed_at", "created_at", "updated_at"),
    delete_handler=close_slave_sessions,
    allow_owner_delete=True,
)

router = APIRouter(prefix="/slave_sessions", tags=["crud-slave-sessions"])


@router.post("/list", response_model=CrudListResponse)
async def api_list_slave_sessions(
    request: CrudListRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_crud_user),
) -> CrudListResponse:
    return await list_rows(db, CRUD_SPEC, request, current_user)


@router.get("/{row_id}", response_model=dict[str, Any])
async def api_get_slave_session(
    row_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_crud_user),
) -> dict[str, Any]:
    return await get_row(db, CRUD_SPEC, row_id, current_user)


@router.post("/delete", response_model=CrudDeleteResponse)
async def api_delete_slave_sessions(
    request: CrudDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_crud_user),
) -> CrudDeleteResponse:
    return await delete_rows(db, CRUD_SPEC, request, current_user)
