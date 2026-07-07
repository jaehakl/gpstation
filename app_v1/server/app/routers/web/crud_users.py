from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import UserData
from app.routers.web.crud_auth import require_crud_user
from app.routers.web.models import (
    CrudDeleteRequest,
    CrudDeleteResponse,
    CrudListRequest,
    CrudListResponse,
    CrudUpsertRequest,
    CrudUpsertResponse,
)
from app.user_auth.db import User
from app.utils.crud import CrudSpec, delete_rows, get_row, list_rows, upsert_rows

ALLOWED_CRUD_USER_ROLES = {"admin", "user", "unauthorized"}


def validate_user_payload(_spec: CrudSpec, field_name: str, value: Any) -> None:
    if field_name == "role" and value not in ALLOWED_CRUD_USER_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")


CRUD_SPEC = CrudSpec(
    model=User,
    public_fields=(
        "id",
        "email",
        "username",
        "display_name",
        "role",
        "status",
        "created_at",
        "updated_at",
        "access_key_ids",
        "launcher_ids",
        "slave_session_ids",
    ),
    writable_fields=("email", "username", "display_name", "role", "status"),
    owner_field="id",
    searchable_fields=("email", "username", "display_name", "role", "status"),
    sortable_fields=("email", "username", "display_name", "role", "status", "created_at", "updated_at"),
    delete_mode="physical",
    required_fields=("role", "status"),
    validate_payload=validate_user_payload,
    allow_owner_delete=True,
    computed_fields={
        "access_key_ids": lambda user: [access_key.id for access_key in user.access_keys],
        "launcher_ids": lambda user: [launcher.id for launcher in user.launchers],
        "slave_session_ids": lambda user: [slave_session.id for slave_session in user.slave_sessions],
    },
    relationship_loads=("access_keys", "launchers", "slave_sessions"),
)

router = APIRouter(prefix="/users", tags=["crud-users"])


@router.post("/list", response_model=CrudListResponse)
async def api_list_users(
    request: CrudListRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_crud_user),
) -> CrudListResponse:
    return await list_rows(db, CRUD_SPEC, request, current_user)


@router.get("/{row_id}", response_model=dict[str, Any])
async def api_get_user(
    row_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_crud_user),
) -> dict[str, Any]:
    return await get_row(db, CRUD_SPEC, row_id, current_user)


@router.post("/upsert", response_model=list[CrudUpsertResponse])
async def api_upsert_users(
    request: CrudUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_crud_user),
) -> list[CrudUpsertResponse]:
    return await upsert_rows(db, CRUD_SPEC, request, current_user)


@router.post("/delete", response_model=CrudDeleteResponse)
async def api_delete_users(
    request: CrudDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserData = Depends(require_crud_user),
) -> CrudDeleteResponse:
    return await delete_rows(db, CRUD_SPEC, request, current_user)
