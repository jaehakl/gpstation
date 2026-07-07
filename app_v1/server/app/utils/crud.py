from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Literal

from fastapi import HTTPException, status
from sqlalchemy import Text, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import UserData
from app.routers.crud.models import (
    CrudDeleteRequest,
    CrudDeleteResponse,
    CrudListRequest,
    CrudListResponse,
    CrudUpsertRequest,
    CrudUpsertResponse,
)

DeleteMode = Literal["physical"]
PayloadValidator = Callable[["CrudSpec", str, Any], None]
DeleteHandler = Callable[[AsyncSession, "CrudSpec", list[str], Any | None], Awaitable[int]]
ComputedField = Callable[[Any], Any]


@dataclass(frozen=True)
class CrudSpec:
    model: type[Any]
    public_fields: tuple[str, ...]
    writable_fields: tuple[str, ...] = ()
    owner_field: str | None = "user_id"
    searchable_fields: tuple[str, ...] = ()
    sortable_fields: tuple[str, ...] = ()
    delete_mode: DeleteMode | None = None
    default_sort: tuple[str, str] = ("created_at", "desc")
    required_fields: tuple[str, ...] = field(default_factory=tuple)
    validate_payload: PayloadValidator | None = None
    delete_handler: DeleteHandler | None = None
    allow_owner_delete: bool = False
    computed_fields: dict[str, ComputedField] = field(default_factory=dict)
    relationship_loads: tuple[str, ...] = ()


def serialize_entity(entity: Any, spec: CrudSpec) -> dict[str, Any]:
    return {
        field_name: serialize_value(
            spec.computed_fields[field_name](entity) if field_name in spec.computed_fields else getattr(entity, field_name, None)
        )
        for field_name in spec.public_fields
    }


def serialize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def visibility_clause(spec: CrudSpec, current_user: UserData) -> Any | None:
    if current_user.role == "admin":
        return None
    if spec.owner_field is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return getattr(spec.model, spec.owner_field) == current_user.id


def build_search_clause(spec: CrudSpec, request: CrudListRequest) -> Any | None:
    clauses: list[Any] = []
    search_text = (request.search_text or "").strip()
    if search_text:
        search_conditions = build_text_conditions(spec, spec.searchable_fields, search_text)
        if search_conditions:
            clauses.append(or_(*search_conditions))

    for field_name, values in request.text_filter.items():
        if field_name not in spec.public_fields:
            continue
        field_conditions = []
        for raw_value in values:
            value = raw_value.strip() if isinstance(raw_value, str) else ""
            if value:
                field_conditions.extend(build_text_conditions(spec, (field_name,), value))
        if field_conditions:
            clauses.append(or_(*field_conditions))

    for field_name, bounds in request.filter.items():
        condition = build_range_condition(spec, field_name, bounds)
        if condition is not None:
            clauses.append(condition)

    if not clauses:
        return None
    return and_(*clauses)


def build_text_conditions(spec: CrudSpec, field_names: Iterable[str], value: str) -> list[Any]:
    conditions = []
    for field_name in field_names:
        if field_name not in spec.public_fields:
            continue
        column = spec.model.__table__.columns.get(field_name)
        if column is None:
            continue
        conditions.append(cast(column, Text).ilike(f"%{value}%"))
    return conditions


def build_range_condition(spec: CrudSpec, field_name: str, bounds: list[Any]) -> Any | None:
    if field_name not in spec.public_fields:
        return None
    column = spec.model.__table__.columns.get(field_name)
    if column is None:
        return None
    python_type = get_python_type(column)
    values = list(bounds or [])
    min_value = coerce_filter_bound(values[0], python_type) if len(values) > 0 else None
    max_value = coerce_filter_bound(values[1], python_type) if len(values) > 1 else None
    clauses = []
    if min_value is not None:
        clauses.append(column >= min_value)
    if max_value is not None:
        clauses.append(column <= max_value)
    if not clauses:
        return None
    return and_(*clauses)


def get_python_type(column: Any) -> type[Any] | None:
    try:
        return column.type.python_type
    except (AttributeError, NotImplementedError):
        return None


def coerce_filter_bound(value: Any, python_type: type[Any] | None) -> Any | None:
    if value is None:
        return None
    try:
        if python_type is int:
            return int(value)
        if python_type is float:
            return float(value)
        if python_type is datetime:
            return parse_datetime(value)
    except (TypeError, ValueError):
        return None
    return None


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError("Invalid datetime")


def build_order_by(spec: CrudSpec, request: CrudListRequest) -> list[Any]:
    field_name = spec.default_sort[0]
    direction = spec.default_sort[1]
    if request.sort:
        requested_field = request.sort[0] if len(request.sort) > 0 else ""
        requested_direction = request.sort[1] if len(request.sort) > 1 else "asc"
        if requested_field in spec.sortable_fields or requested_field == "id":
            field_name = requested_field
            direction = "desc" if requested_direction.lower() == "desc" else "asc"

    if field_name not in spec.public_fields or field_name not in spec.model.__table__.columns:
        field_name = "id"
        direction = "asc"

    column = getattr(spec.model, field_name)
    return [column.desc() if direction == "desc" else column.asc()]


async def list_rows(
    db: AsyncSession,
    spec: CrudSpec,
    request: CrudListRequest,
    current_user: UserData,
) -> CrudListResponse:
    clauses = [clause for clause in (visibility_clause(spec, current_user), build_search_clause(spec, request)) if clause is not None]
    if request.selected_ids:
        clauses.append(spec.model.id.in_(list(dict.fromkeys(request.selected_ids))))
    where_clause = and_(*clauses) if clauses else None

    count_stmt = select(func.count()).select_from(spec.model)
    stmt = select(spec.model).options(*build_relationship_options(spec)).order_by(*build_order_by(spec, request))
    if where_clause is not None:
        count_stmt = count_stmt.where(where_clause)
        stmt = stmt.where(where_clause)
    if request.offset:
        stmt = stmt.offset(request.offset)
    if request.limit is not None:
        stmt = stmt.limit(request.limit)

    total = await db.scalar(count_stmt)
    rows = (await db.execute(stmt)).scalars().all()
    return CrudListResponse(total=int(total or 0), items=[serialize_entity(row, spec) for row in rows])


async def get_row(
    db: AsyncSession,
    spec: CrudSpec,
    row_id: str,
    current_user: UserData,
) -> dict[str, Any]:
    clauses = [spec.model.id == row_id]
    visibility = visibility_clause(spec, current_user)
    if visibility is not None:
        clauses.append(visibility)
    row = await db.scalar(select(spec.model).options(*build_relationship_options(spec)).where(and_(*clauses)))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CRUD row not found")
    return serialize_entity(row, spec)


async def upsert_rows(
    db: AsyncSession,
    spec: CrudSpec,
    request: CrudUpsertRequest,
    current_user: UserData,
) -> list[CrudUpsertResponse]:
    require_admin(current_user)
    if not spec.writable_fields:
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="CRUD upsert is not supported for this table")

    results: list[CrudUpsertResponse] = []
    for item in request.items:
        row_id = item.get("id")
        entity = await db.get(spec.model, row_id) if row_id else None
        if entity is None:
            entity = spec.model()
            db.add(entity)

        for field_name, value in item.items():
            if field_name == "id" or field_name not in spec.writable_fields:
                continue
            if field_name in spec.required_fields and value is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} cannot be null")
            if spec.validate_payload is not None:
                spec.validate_payload(spec, field_name, value)
            setattr(entity, field_name, coerce_payload_value(spec, field_name, value))

        await db.flush()
        results.append(CrudUpsertResponse(id=str(entity.id)))

    await db.commit()
    return results


def coerce_payload_value(spec: CrudSpec, field_name: str, value: Any) -> Any:
    if value is None:
        return None
    column = spec.model.__table__.columns.get(field_name)
    if column is None:
        return value
    python_type = get_python_type(column)
    if python_type is datetime:
        return parse_datetime(value)
    return value


async def delete_rows(
    db: AsyncSession,
    spec: CrudSpec,
    request: CrudDeleteRequest,
    current_user: UserData,
) -> CrudDeleteResponse:
    ids = list(dict.fromkeys(request.ids))
    if not ids:
        return CrudDeleteResponse(deleted=0)
    owner_clause = delete_owner_clause(spec, current_user)
    if spec.delete_handler is not None:
        return CrudDeleteResponse(deleted=await spec.delete_handler(db, spec, ids, owner_clause))
    if spec.delete_mode is None:
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="CRUD delete is not supported for this table")

    clauses = [spec.model.id.in_(ids)]
    if owner_clause is not None:
        clauses.append(owner_clause)
    rows = (await db.execute(select(spec.model).where(and_(*clauses)))).scalars().all()
    for row in rows:
        if spec.delete_mode == "physical":
            await db.delete(row)

    await db.commit()
    return CrudDeleteResponse(deleted=len(rows))


def require_admin(current_user: UserData) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def delete_owner_clause(spec: CrudSpec, current_user: UserData) -> Any | None:
    if current_user.role == "admin":
        return None
    if not spec.allow_owner_delete or spec.owner_field is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return getattr(spec.model, spec.owner_field) == current_user.id


def build_relationship_options(spec: CrudSpec) -> list[Any]:
    return [selectinload(getattr(spec.model, relationship_name)) for relationship_name in spec.relationship_loads]
