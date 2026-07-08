from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Launcher, get_db
from app.models import UserData
from app.routers.web.crud_auth import require_crud_user
from app.routers.web.models import CrudListRequest, CrudListResponse
from app.utils.crud import CrudSpec, get_row, list_rows

CRUD_SPEC = CrudSpec(
    model=Launcher,
    public_fields=(
        "id",
        "user_id",
        "launcher_name",
        "ip_address",
        "status",
        "slave_app_ids",
        "connected_at",
        "last_heartbeat_at",
        "disconnected_at",
        "created_at",
        "updated_at",
    ),
    searchable_fields=("launcher_name", "ip_address", "status", "slave_app_ids"),
    sortable_fields=("launcher_name", "status", "connected_at", "last_heartbeat_at", "disconnected_at", "created_at", "updated_at"),
    default_sort=("last_heartbeat_at", "desc"),
)

router = APIRouter(prefix="/launchers", tags=["crud-launchers"])


@router.post("/list", response_model=CrudListResponse)
async def api_list_launchers(
    request: CrudListRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_crud_user),
) -> CrudListResponse:
    return await list_rows(db, CRUD_SPEC, request, current_user)


@router.get("/{row_id}", response_model=dict[str, Any])
async def api_get_launcher(
    row_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_crud_user),
) -> dict[str, Any]:
    return await get_row(db, CRUD_SPEC, row_id, current_user)
