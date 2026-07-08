from __future__ import annotations

from fastapi import APIRouter

from app.routers.web import crud_access_keys, crud_launchers, crud_users

router = APIRouter(prefix="/crud", tags=["crud"])
router.include_router(crud_users.router)
router.include_router(crud_access_keys.router)
router.include_router(crud_launchers.router)
