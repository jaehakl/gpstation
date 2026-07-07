from __future__ import annotations

from fastapi import APIRouter

from app.routers.crud import access_keys, launchers, slave_sessions, users

router = APIRouter(prefix="/crud", tags=["crud"])
router.include_router(users.router)
router.include_router(access_keys.router)
router.include_router(launchers.router)
router.include_router(slave_sessions.router)
